"""Tests for ESPHomeBluetoothDevice."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import Mock

import pytest
from bleak_retry_connector import Allocations

from bleak_esphome.backend.device import (
    MAX_TRACKED_UNANSWERED_CONNECTS,
    ESPHomeBluetoothDevice,
)

from ._helpers import ESP_MAC_ADDRESS

# The streak map is keyed on the int address, as the sibling maps are.
ADDRESS = 0xCCBBAADDEEFF


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_returns_immediately_when_free(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Return current count without suspending when a slot is already free."""
    bluetooth_device.ble_connections_free = 3
    assert await bluetooth_device.wait_for_ble_connections_free(1.0) == 3


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_resolves_on_update(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Suspended waiter wakes when the update reports a free slot."""
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(1.0))
    await asyncio.sleep(0)
    assert not task.done()
    bluetooth_device.async_update_ble_connection_limits(2, 5, [10, 20, 30])
    assert await task == 2
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_timeout(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Waiting with no available slot raises ``TimeoutError`` after deadline."""
    bluetooth_device.ble_connections_limit = 3
    bluetooth_device.ble_connections_free = 0
    with pytest.raises(TimeoutError) as exc_info:
        await bluetooth_device.wait_for_ble_connections_free(0.001)
    # The timeout must name the saturated proxy and its slot state so the
    # failure is actionable rather than an anonymous timeout.
    message = str(exc_info.value)
    assert bluetooth_device.name in message
    assert "AA:BB:CC:DD:EE:FF" in message
    assert "limit=3" in message
    assert "in use=3" in message
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_cancellation_cleans_up(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Cancelling the waiter must remove the pending future from the list."""
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(10.0))
    await asyncio.sleep(0)
    assert len(bluetooth_device._ble_connection_free_futures) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_reconcile_skips_untrusted_allocated_list(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """
    An allocated list shorter than the used slot count is not trusted.

    Older firmware reports free/limit without the allocated list at all,
    which looks like a length mismatch and must not disconnect tracked
    clients.
    """
    handler = Mock()
    bluetooth_device.async_track_client(42, handler)
    bluetooth_device.async_update_ble_connection_limits(1, 3, [])
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_only_disconnects_missing_addresses(
    bluetooth_device: ESPHomeBluetoothDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the clients missing from the allocated list are disconnected."""
    stale = Mock()
    live = Mock()
    bluetooth_device.async_track_client(42, stale)
    bluetooth_device.async_track_client(43, live)
    with caplog.at_level(logging.WARNING):
        bluetooth_device.async_update_ble_connection_limits(2, 3, [43])
    stale.assert_called_once_with()
    live.assert_not_called()
    # Out of sync state is a failure somewhere; it must surface without
    # debug logging enabled.
    assert "Reconciling stale connection" in caplog.text


@pytest.mark.asyncio
async def test_reconcile_isolates_raising_handler(
    bluetooth_device: ESPHomeBluetoothDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    A raising disconnect handler must not strand the other stale clients.

    The handler ends in consumer supplied code; if one raises, the loop
    logs it and still reconciles the remaining stale clients rather than
    leaving them phantom until the next slot change.
    """
    boom = Mock(side_effect=RuntimeError("boom"))
    ok = Mock()
    bluetooth_device.async_track_client(42, boom)
    bluetooth_device.async_track_client(43, ok)
    with caplog.at_level(logging.WARNING):
        bluetooth_device.async_update_ble_connection_limits(3, 3, [])
    boom.assert_called_once_with()
    ok.assert_called_once_with()
    assert "Error reconciling stale connection" in caplog.text
    # The raising client was untracked before invocation, so a later update
    # does not retry it and re-fire the warning plus traceback.
    caplog.clear()
    bluetooth_device.async_update_ble_connection_limits(3, 3, [])
    boom.assert_called_once_with()
    assert "Reconciling stale connection" not in caplog.text


@pytest.mark.asyncio
async def test_track_client_logs_when_displacing_existing_entry(
    bluetooth_device: ESPHomeBluetoothDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Displacing a tracked client for the same address leaves a trace."""
    old_handler = Mock()
    new_handler = Mock()
    bluetooth_device.async_track_client(42, old_handler)
    with caplog.at_level(logging.DEBUG):
        bluetooth_device.async_track_client(42, new_handler)
    assert "Replacing tracked client" in caplog.text


@pytest.mark.asyncio
async def test_reconcile_warns_once_on_slot_accounting_anomaly(
    bluetooth_device: ESPHomeBluetoothDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    A mismatch on list-reporting firmware warns once until it recovers.

    Legacy firmware that never reports the list stays at debug; firmware
    that has reported it and then mismatches has a genuine accounting
    anomaly that disables the heal, which must be visible in production
    logs, once per episode.
    """
    handler = Mock()
    bluetooth_device.async_track_client(42, handler)
    with caplog.at_level(logging.WARNING):
        # Legacy-looking mismatch before any list was seen: no warning.
        bluetooth_device.async_update_ble_connection_limits(1, 3, [])
        assert "slot accounting is inconsistent" not in caplog.text
        # The list is reported, then mismatches: warn once.
        bluetooth_device.async_update_ble_connection_limits(1, 3, [42, 43])
        bluetooth_device.async_update_ble_connection_limits(1, 3, [42])
        assert caplog.text.count("slot accounting is inconsistent") == 1
        bluetooth_device.async_update_ble_connection_limits(1, 3, [43])
        assert caplog.text.count("slot accounting is inconsistent") == 1
        # A matching update re-arms the warning for the next episode.
        bluetooth_device.async_update_ble_connection_limits(1, 3, [42, 43])
        bluetooth_device.async_update_ble_connection_limits(1, 3, [42])
        assert caplog.text.count("slot accounting is inconsistent") == 2
    handler.assert_not_called()


@pytest.mark.asyncio
async def test_untrack_client_only_removes_matching_handler(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Untracking with a stale handler must not evict a newer client."""
    old_handler = Mock()
    new_handler = Mock()
    bluetooth_device.async_track_client(42, new_handler)
    bluetooth_device.async_untrack_client(42, old_handler)
    bluetooth_device.async_update_ble_connection_limits(3, 3, [])
    new_handler.assert_called_once_with()

    bluetooth_device.async_untrack_client(42, new_handler)
    new_handler.reset_mock()
    bluetooth_device.async_update_ble_connection_limits(3, 3, [])
    new_handler.assert_not_called()


@pytest.mark.asyncio
async def test_set_unavailable_fails_pending_slot_waiters(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A parked slot waiter fails fast when the proxy goes unavailable."""
    bluetooth_device.available = True
    # Seed real session state so the clearing assertions below are not
    # satisfied vacuously by the fixture's empty defaults; free stays
    # zero so the waiter parks.
    bluetooth_device.async_update_ble_connection_limits(0, 2, [42, 43])
    pushed: list[Allocations] = []
    bluetooth_device.async_subscribe_connection_slots(pushed.append)
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(60.0))
    await asyncio.sleep(0)
    assert not task.done()
    bluetooth_device.async_set_unavailable()
    with pytest.raises(TimeoutError, match="Proxy became unavailable"):
        await task
    assert bluetooth_device.available is False
    assert bluetooth_device._ble_connection_free_futures == set()
    # The dead session's allocated list and free count must not survive
    # into a reuse, and the cleared snapshot is pushed so the
    # subscriber's stored copy does not keep the stale state either.
    assert bluetooth_device.ble_allocations == []
    assert bluetooth_device.ble_connections_free == 0
    assert pushed[-1].allocated == []
    assert pushed[-1].free == 0


@pytest.mark.asyncio
async def test_update_isolates_raising_subscriber(
    bluetooth_device: ESPHomeBluetoothDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A raising slot subscriber must not abort a slot report."""
    bluetooth_device.async_subscribe_connection_slots(
        Mock(side_effect=ValueError("subscriber boom"))
    )
    with caplog.at_level(logging.ERROR):
        bluetooth_device.async_update_ble_connection_limits(1, 3, [42])
    # The report itself still landed.
    assert bluetooth_device.ble_connections_free == 1
    assert "Error pushing allocations" in caplog.text
    # The failed push keeps the first snapshot forced push armed: an
    # identical update retries once the subscriber heals.
    pushed: list[Allocations] = []
    bluetooth_device._connection_slots_callback = pushed.append
    bluetooth_device.async_update_ble_connection_limits(1, 3, [42])
    assert len(pushed) == 1


@pytest.mark.asyncio
async def test_failed_cleared_push_rearms_the_forced_push(
    bluetooth_device: ESPHomeBluetoothDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed cleared snapshot push re-arms the forced push."""
    bluetooth_device.available = True
    good: list[Allocations] = []
    bluetooth_device.async_subscribe_connection_slots(good.append)
    bluetooth_device.async_update_ble_connection_limits(1, 3, [42])
    assert len(good) == 1
    bluetooth_device._connection_slots_callback = Mock(
        side_effect=ValueError("subscriber boom")
    )
    with caplog.at_level(logging.ERROR):
        bluetooth_device.async_set_unavailable()
    # The subscriber heals; an update matching the zeroed state still
    # pushes because the failed clear re-armed the forced push.
    bluetooth_device._connection_slots_callback = good.append
    bluetooth_device.async_update_ble_connection_limits(0, 3, [])
    assert len(good) == 2
    assert good[-1].free == 0


@pytest.mark.asyncio
async def test_set_unavailable_skips_push_when_nothing_to_clear(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """An already zeroed device pushes nothing on unavailability."""
    pushed: list[Allocations] = []
    bluetooth_device.async_subscribe_connection_slots(pushed.append)
    bluetooth_device.async_set_unavailable()
    assert pushed == []
    # Idempotent: a second call also pushes nothing.
    bluetooth_device.async_set_unavailable()
    assert pushed == []


@pytest.mark.asyncio
async def test_set_unavailable_publishes_zeroed_free_for_idle_proxy(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """
    An idle proxy dying still publishes its zeroed free count.

    With no allocations to clear, the free count is the only cleared
    fact; the push must still fire so the subscriber's cached snapshot
    does not keep advertising free slots on a dead proxy.
    """
    bluetooth_device.available = True
    bluetooth_device.async_update_ble_connection_limits(3, 3, [])
    pushed: list[Allocations] = []
    bluetooth_device.async_subscribe_connection_slots(pushed.append)
    bluetooth_device.async_set_unavailable()
    assert pushed[-1].free == 0
    assert pushed[-1].allocated == []


@pytest.mark.asyncio
async def test_set_unavailable_raising_subscriber_does_not_strand_waiters(
    bluetooth_device: ESPHomeBluetoothDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    A raising slot subscriber cannot strand the parked waiters.

    The waiters are failed before the cleared snapshot push runs, and
    the push itself is guarded because it ends in consumer supplied
    code, so ``async_set_unavailable`` never raises.
    """
    bluetooth_device.available = True
    bluetooth_device.async_update_ble_connection_limits(0, 2, [42, 43])
    bluetooth_device.async_subscribe_connection_slots(
        Mock(side_effect=ValueError("subscriber boom"))
    )
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(60.0))
    await asyncio.sleep(0)
    assert not task.done()

    with caplog.at_level(logging.ERROR):
        bluetooth_device.async_set_unavailable()

    with pytest.raises(TimeoutError, match="Proxy became unavailable"):
        await task
    assert bluetooth_device.ble_allocations == []
    assert "Error pushing allocations" in caplog.text


@pytest.mark.asyncio
async def test_wait_after_unavailable_fails_fast(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A waiter entering after the proxy went away fails immediately."""
    bluetooth_device.async_set_unavailable()
    with pytest.raises(TimeoutError, match="Proxy became unavailable"):
        await bluetooth_device.wait_for_ble_connections_free(60.0)
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_slot_update_clears_the_unavailability_latch(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A proxy reporting slot state again clears the fail fast latch."""
    bluetooth_device.async_set_unavailable()
    with pytest.raises(TimeoutError, match="Proxy became unavailable"):
        await bluetooth_device.wait_for_ble_connections_free(60.0)
    bluetooth_device.async_update_ble_connection_limits(2, 3, [42])
    assert await bluetooth_device.wait_for_ble_connections_free(60.0) == 2


@pytest.mark.asyncio
async def test_reuse_after_unavailable_does_not_trust_stale_free_count(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """
    A reused device must not serve the dead session's free count.

    ``async_set_unavailable`` zeroes ``ble_connections_free``, so a
    caller that restores ``available`` on reconnect parks for the new
    session's first slot report instead of getting an immediate return
    from a count the dead session left behind.
    """
    bluetooth_device.available = True
    bluetooth_device.async_update_ble_connection_limits(2, 3, [42])
    bluetooth_device.async_set_unavailable()
    assert bluetooth_device.ble_connections_free == 0
    assert bluetooth_device.ble_connections_limit == 3
    bluetooth_device.available = True
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(60.0))
    await asyncio.sleep(0)
    assert not task.done()
    bluetooth_device.async_update_ble_connection_limits(1, 3, [43])
    assert await task == 1


@pytest.mark.asyncio
async def test_restoring_available_disarms_the_fail_fast(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """
    A reuser restoring ``available`` disarms the fail fast immediately.

    The latch itself only clears on the next slot report, but a caller
    that marked the device available again must not have its waiters
    failed by the stale latch in the meantime.
    """
    bluetooth_device.async_set_unavailable()
    bluetooth_device.available = True
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(60.0))
    await asyncio.sleep(0)
    assert not task.done()
    bluetooth_device.async_update_ble_connection_limits(1, 3, [42])
    assert await task == 1


@pytest.mark.asyncio
async def test_saturated_slot_update_clears_the_unavailability_latch(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """
    A ``free=0`` slot report also clears the fail fast latch.

    A saturated proxy is alive, not dead; the reset is deliberately
    unconditional at the top of the update, so a waiter parks for a slot
    instead of failing fast.
    """
    bluetooth_device.async_set_unavailable()
    bluetooth_device.async_update_ble_connection_limits(0, 3, [])
    task = asyncio.create_task(bluetooth_device.wait_for_ble_connections_free(60.0))
    await asyncio.sleep(0)
    # The waiter parks rather than raising immediately.
    assert not task.done()
    bluetooth_device.async_update_ble_connection_limits(1, 3, [42])
    assert await task == 1


@pytest.mark.asyncio
async def test_set_unavailable_skips_done_futures(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A done future is skipped while a pending one still fails fast."""
    loop = asyncio.get_running_loop()
    done_fut: asyncio.Future[int] = loop.create_future()
    done_fut.cancel()
    pending_fut: asyncio.Future[int] = loop.create_future()
    bluetooth_device._ble_connection_free_futures.update({done_fut, pending_fut})
    bluetooth_device.async_set_unavailable()
    assert done_fut.cancelled()
    with pytest.raises(TimeoutError, match="Proxy became unavailable"):
        await pending_fut
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_wait_for_ble_connections_free_timer_after_result_does_not_raise(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Late-firing timeout must not raise on an already-resolved future."""
    fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    fut.set_result(1)
    bluetooth_device._wait_for_ble_connections_free_timeout(fut)
    assert fut.result() == 1


@pytest.mark.asyncio
async def test_async_update_ble_connection_limits_skips_done_futures(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A future already resolved (e.g. cancelled) is skipped on update."""
    done_fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    done_fut.cancel()
    pending_fut: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    bluetooth_device._ble_connection_free_futures.update([done_fut, pending_fut])
    bluetooth_device.async_update_ble_connection_limits(4, 4, [])
    assert pending_fut.done()
    assert pending_fut.result() == 4
    assert bluetooth_device._ble_connection_free_futures == set()


@pytest.mark.asyncio
async def test_subscribe_connection_slots_fires_on_first_update(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """First update always invokes the callback even when values unchanged."""
    callback = Mock()
    bluetooth_device.async_subscribe_connection_slots(callback)
    bluetooth_device.async_update_ble_connection_limits(0, 0, [])
    callback.assert_called_once()
    allocation = callback.call_args[0][0]
    assert isinstance(allocation, Allocations)
    assert allocation.adapter == ESP_MAC_ADDRESS
    assert allocation.slots == 0
    assert allocation.free == 0
    assert allocation.allocated == []


@pytest.mark.asyncio
async def test_subscribe_connection_slots_skips_when_unchanged(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Repeat updates with identical values do not refire the callback."""
    callback = Mock()
    bluetooth_device.async_subscribe_connection_slots(callback)
    bluetooth_device.async_update_ble_connection_limits(1, 2, [42])
    bluetooth_device.async_update_ble_connection_limits(1, 2, [42])
    assert callback.call_count == 1


@pytest.mark.asyncio
async def test_subscribe_connection_slots_fires_on_change(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Each distinct update triggers the subscriber callback."""
    callback = Mock()
    bluetooth_device.async_subscribe_connection_slots(callback)
    bluetooth_device.async_update_ble_connection_limits(0, 2, [])
    bluetooth_device.async_update_ble_connection_limits(1, 2, [99])
    bluetooth_device.async_update_ble_connection_limits(2, 2, [])
    assert callback.call_count == 3
    third = callback.call_args_list[2][0][0]
    assert third.free == 2
    assert third.slots == 2
    assert third.allocated == []


@pytest.mark.asyncio
async def test_note_connect_timeout_counts_consecutive_attempts(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Each unanswered connect request advances that address's streak."""
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 1
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 2
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 3


@pytest.mark.asyncio
async def test_note_connect_response_clears_streak(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A reported connection state resets the streak for that address."""
    bluetooth_device.async_note_connect_timeout(ADDRESS)
    bluetooth_device.async_note_connect_timeout(ADDRESS)
    bluetooth_device.async_note_connect_response(ADDRESS)
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 1


@pytest.mark.asyncio
async def test_note_connect_response_without_streak_is_a_noop(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Clearing an address that never timed out must not raise."""
    bluetooth_device.async_note_connect_response(ADDRESS)
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 1


@pytest.mark.asyncio
async def test_connect_streaks_are_tracked_per_address(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """One unreachable device must not mask another on the same proxy."""
    other = ADDRESS + 1
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 1
    assert bluetooth_device.async_note_connect_timeout(other) == 1
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 2
    bluetooth_device.async_note_connect_response(ADDRESS)
    assert bluetooth_device.async_note_connect_timeout(other) == 2
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 1


@pytest.mark.asyncio
async def test_connect_timeout_streaks_are_bounded(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """
    The streak map must not grow without bound.

    An address that times out once and is never seen again has nothing to
    clear its entry, so a peripheral rotating its address would otherwise
    leave one behind for the life of the proxy connection.
    """
    overflow = 50
    for index in range(MAX_TRACKED_UNANSWERED_CONNECTS + overflow):
        bluetooth_device.async_note_connect_timeout(ADDRESS + 1 + index)

    assert len(bluetooth_device._unanswered_connects) == (
        MAX_TRACKED_UNANSWERED_CONNECTS
    )


@pytest.mark.asyncio
async def test_connect_timeout_streaks_evict_the_least_recently_used(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """Eviction must drop the stalest address, never the one still failing."""
    still_failing = ADDRESS
    bluetooth_device.async_note_connect_timeout(still_failing)

    # Keep it the most recently used while pushing the rest past the bound.
    for index in range(MAX_TRACKED_UNANSWERED_CONNECTS * 2):
        bluetooth_device.async_note_connect_timeout(ADDRESS + 1 + index)
        bluetooth_device.async_note_connect_timeout(still_failing)

    # One initial note, one per loop iteration, then the call below: an exact
    # count, so an eviction that silently reset it could not slip through.
    expected = 1 + MAX_TRACKED_UNANSWERED_CONNECTS * 2 + 1
    assert bluetooth_device.async_note_connect_timeout(still_failing) == expected


@pytest.mark.asyncio
async def test_set_unavailable_clears_connect_streaks(
    bluetooth_device: ESPHomeBluetoothDevice,
) -> None:
    """A dead session's streaks must not survive into the next one."""
    bluetooth_device.async_note_connect_timeout(ADDRESS)
    bluetooth_device.async_note_connect_timeout(ADDRESS)
    bluetooth_device.async_set_unavailable()
    assert bluetooth_device.async_note_connect_timeout(ADDRESS) == 1
