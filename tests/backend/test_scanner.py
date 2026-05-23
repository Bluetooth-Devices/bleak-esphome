import asyncio
from unittest.mock import MagicMock

import pytest
from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    BluetoothLEAdvertisement,
    BluetoothLERawAdvertisement,
    BluetoothLERawAdvertisementsResponse,
    BluetoothScannerMode,
    BluetoothScannerState,
    BluetoothScannerStateResponse,
)
from bluetooth_data_tools import int_to_bluetooth_address
from habluetooth import (
    Allocations,
    BaseHaRemoteScanner,
    BluetoothScanningMode,
    HaBluetoothConnector,
    get_manager,
)

from bleak_esphome.backend.client import ESPHomeClientData
from bleak_esphome.backend.device import ESPHomeBluetoothDevice
from bleak_esphome.backend.scanner import ESPHomeScanner

from ._helpers import ESP_MAC_ADDRESS, ESP_NAME


@pytest.fixture
def scanner() -> ESPHomeScanner:
    """Fixture to create an ESPHomeScanner instance."""
    connector = HaBluetoothConnector(ESPHomeClientData, ESP_MAC_ADDRESS, lambda: True)
    return ESPHomeScanner(ESP_MAC_ADDRESS, ESP_NAME, connector, True)


def test_scanner(scanner: ESPHomeScanner) -> None:
    assert isinstance(scanner, BaseHaRemoteScanner)


def test_scanner_async_on_advertisement_decoded(scanner: ESPHomeScanner) -> None:
    """Cover the decoded (non-raw) advertisement path."""
    address_int = 261602360644300
    adv = BluetoothLEAdvertisement(
        address=address_int,
        rssi=-72,
        address_type=1,
        name="decoded-device",
        service_uuids=["0000fe07-0000-1000-8000-00805f9b34fb"],
        service_data={"0000fe07-0000-1000-8000-00805f9b34fb": b"\x01\x02"},
        manufacturer_data={0x05: b"\xaa\xbb"},
    )
    scanner.async_on_advertisement(adv)
    manager = get_manager()
    service_info = manager.async_last_service_info(
        int_to_bluetooth_address(address_int), True
    )
    assert service_info is not None
    assert service_info.name == "decoded-device"
    assert service_info.rssi == -72
    assert service_info.manufacturer_data == {0x05: b"\xaa\xbb"}


def test_scanner_async_on_raw_advertisements(scanner: ESPHomeScanner) -> None:
    adv = BluetoothLERawAdvertisementsResponse(
        advertisements=[
            BluetoothLERawAdvertisement(
                address=261602360644300,
                rssi=-96,
                address_type=1,
                data=b"\x02\x01\x04\x03\x03\x07\xfe\x18\xff\x97\x05\x06\x00\x16p%\x00\xca\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x02\n\x00",
            ),
            BluetoothLERawAdvertisement(
                address=246965243285491,
                rssi=-88,
                address_type=1,
                data=b"\x02\x01\x1a\x1b\xffu\x00B\x04\x01\x01o\xe0\x8d\x17\xe7\x0f\xf3\xe2\x8d\x17\xe7\x0f\xf2(\x00\x00\x00\x00\x00\x00",
            ),
        ]
    )
    scanner.async_on_raw_advertisements(adv)
    manager = get_manager()
    assert manager.async_last_service_info(
        int_to_bluetooth_address(261602360644300), True
    )
    assert manager.async_last_service_info(
        int_to_bluetooth_address(246965243285491), True
    )


def test_scanner_async_update_scanner_state(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """Running scanner reports both current and requested mode."""
    mock_client.subscribe_bluetooth_scanner_state(scanner.async_update_scanner_state)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.ACTIVE,
        )
    )
    assert scanner.current_mode == BluetoothScanningMode.ACTIVE
    assert scanner.requested_mode == BluetoothScanningMode.ACTIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert scanner.current_mode == BluetoothScanningMode.PASSIVE
    assert scanner.requested_mode == BluetoothScanningMode.PASSIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=None,
        )
    )
    assert scanner.current_mode is None
    assert scanner.requested_mode is None


@pytest.mark.parametrize(
    "non_running_state",
    [
        BluetoothScannerState.IDLE,
        BluetoothScannerState.STARTING,
        BluetoothScannerState.STOPPING,
        BluetoothScannerState.STOPPED,
        BluetoothScannerState.FAILED,
    ],
)
def test_scanner_state_non_running_clears_current_mode(
    scanner: ESPHomeScanner, non_running_state: BluetoothScannerState
) -> None:
    """Non-RUNNING scanner states keep requested_mode but clear current_mode."""
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.ACTIVE,
        )
    )
    assert scanner.current_mode == BluetoothScanningMode.ACTIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=non_running_state,
            mode=BluetoothScannerMode.ACTIVE,
        )
    )
    assert scanner.current_mode is None
    assert scanner.requested_mode == BluetoothScanningMode.ACTIVE


def test_scanner_state_running_after_failed_restores_current_mode(
    scanner: ESPHomeScanner,
) -> None:
    """current_mode comes back when the scanner resumes RUNNING."""
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.FAILED,
            mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert scanner.current_mode is None
    assert scanner.requested_mode == BluetoothScanningMode.PASSIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert scanner.current_mode == BluetoothScanningMode.PASSIVE
    assert scanner.requested_mode == BluetoothScanningMode.PASSIVE


@pytest.mark.asyncio
async def test_scanner_get_allocations_no_device(scanner: ESPHomeScanner) -> None:
    """Test get_allocations returns None when no bluetooth device is set."""
    assert scanner.get_allocations() is None


@pytest.mark.asyncio
async def test_scanner_get_allocations_no_limit(scanner: ESPHomeScanner) -> None:
    """Test get_allocations returns None when device has no connection limit."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 0
    device.ble_connections_free = 0
    scanner.set_bluetooth_device(device)
    assert scanner.get_allocations() is None


@pytest.mark.asyncio
async def test_scanner_get_allocations_with_device(scanner: ESPHomeScanner) -> None:
    """Test get_allocations returns correct allocation info when device is set."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 3
    device.ble_connections_free = 2
    device.ble_allocations = [123456789]  # Example allocated address

    scanner.set_bluetooth_device(device)
    allocations = scanner.get_allocations()

    assert allocations is not None
    assert isinstance(allocations, Allocations)
    assert allocations.adapter == ESP_MAC_ADDRESS
    assert allocations.slots == 3
    assert allocations.free == 2
    assert allocations.allocated == [int_to_bluetooth_address(123456789)]


@pytest.mark.asyncio
async def test_scanner_get_allocations_no_free_slots(scanner: ESPHomeScanner) -> None:
    """Test get_allocations when all slots are in use."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 2
    device.ble_connections_free = 0
    device.ble_allocations = [111111111, 222222222]

    scanner.set_bluetooth_device(device)
    allocations = scanner.get_allocations()

    assert allocations is not None
    assert allocations.adapter == ESP_MAC_ADDRESS
    assert allocations.slots == 2
    assert allocations.free == 0
    assert allocations.allocated == [
        int_to_bluetooth_address(111111111),
        int_to_bluetooth_address(222222222),
    ]


@pytest.mark.asyncio
async def test_scanner_get_allocations_updates(scanner: ESPHomeScanner) -> None:
    """Test that get_allocations returns current values as they change."""
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    device.ble_connections_limit = 3
    device.ble_connections_free = 3
    device.ble_allocations = []

    scanner.set_bluetooth_device(device)

    # Initial state - all slots free
    allocations = scanner.get_allocations()
    assert allocations is not None
    assert allocations.free == 3
    assert allocations.allocated == []

    # Simulate a connection being made
    device.ble_connections_free = 2
    device.ble_allocations = [987654321]

    # Should return updated values
    allocations = scanner.get_allocations()
    assert allocations is not None
    assert allocations.free == 2
    assert allocations.allocated == [int_to_bluetooth_address(987654321)]

    # Simulate another connection
    device.ble_connections_free = 1
    device.ble_allocations = [987654321, 876543210]

    allocations = scanner.get_allocations()
    assert allocations is not None
    assert allocations.free == 1
    assert allocations.allocated == [
        int_to_bluetooth_address(987654321),
        int_to_bluetooth_address(876543210),
    ]


@pytest.mark.asyncio
async def test_scanner_get_allocations_matches_callback_format(
    scanner: ESPHomeScanner,
) -> None:
    """
    Pull (get_allocations) and push (callback) must report MAC strings.

    Regression for #330: scanner.get_allocations() previously returned raw
    int addresses while ESPHomeBluetoothDevice.async_update_ble_connection_limits
    converted them via int_to_bluetooth_address. Consumers joining the two
    sources saw type-incompatible values.
    """
    device = ESPHomeBluetoothDevice(ESP_NAME, ESP_MAC_ADDRESS)
    captured: list[Allocations] = []
    device.async_subscribe_connection_slots(captured.append)
    scanner.set_bluetooth_device(device)

    raw_addresses = [261602360644300, 246965243285491]
    device.async_update_ble_connection_limits(free=1, limit=3, allocated=raw_addresses)

    pulled = scanner.get_allocations()
    assert pulled is not None
    assert captured
    pushed = captured[-1]

    # Both paths must agree on the address format (MAC strings, not ints).
    expected = [int_to_bluetooth_address(a) for a in raw_addresses]
    assert pulled.allocated == expected
    assert pushed.allocated == expected
    assert all(isinstance(a, str) for a in pulled.allocated)


@pytest.mark.asyncio
async def test_async_request_active_window_no_client(
    scanner: ESPHomeScanner,
) -> None:
    """Without a bound API client the request is a no-op returning False."""
    assert await scanner.async_request_active_window(1.0) is False


@pytest.mark.asyncio
async def test_async_request_active_window_flips_then_restores_passive(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """A passive scanner is flipped to ACTIVE for the window then restored."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    # Start from PASSIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert await scanner.async_request_active_window(0.0) is True
    calls = [c.args for c in mock_client.bluetooth_scanner_set_mode.call_args_list]
    assert calls == [(BluetoothScannerMode.ACTIVE,), (BluetoothScannerMode.PASSIVE,)]


@pytest.mark.asyncio
async def test_async_request_active_window_restores_active_when_proxy_active(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """A proxy already configured ACTIVE returns to ACTIVE after the window."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.ACTIVE,
        )
    )
    assert await scanner.async_request_active_window(0.0) is True
    calls = [c.args for c in mock_client.bluetooth_scanner_set_mode.call_args_list]
    assert calls == [(BluetoothScannerMode.ACTIVE,), (BluetoothScannerMode.ACTIVE,)]


@pytest.mark.asyncio
async def test_async_request_active_window_set_failure_returns_false(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """An APIConnectionError on the entry call yields False; no sleep, no restore."""
    mock_client.bluetooth_scanner_set_mode = MagicMock(
        side_effect=APIConnectionError("boom")
    )
    scanner.set_client(mock_client)
    assert await scanner.async_request_active_window(0.0) is False
    assert mock_client.bluetooth_scanner_set_mode.call_count == 1


@pytest.mark.asyncio
async def test_async_request_active_window_rejects_invalid_duration(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """Negative or non-finite durations are rejected without touching the proxy."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    assert await scanner.async_request_active_window(-1.0) is False
    assert await scanner.async_request_active_window(float("nan")) is False
    assert await scanner.async_request_active_window(float("inf")) is False
    mock_client.bluetooth_scanner_set_mode.assert_not_called()


@pytest.mark.asyncio
async def test_async_request_active_window_restore_failure_swallowed(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """If the restore call fails the window still reports success."""
    call_count = 0

    def fake_set_mode(_mode: BluetoothScannerMode) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise APIConnectionError("restore failed")

    mock_client.bluetooth_scanner_set_mode = MagicMock(side_effect=fake_set_mode)
    scanner.set_client(mock_client)
    assert await scanner.async_request_active_window(0.0) is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_request_active_window_rejects_overlap(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """A second request while a window is open returns False without flipping."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    # Long duration so the first window is still inside asyncio.sleep
    # when the second request arrives. The lock is held for the whole
    # sleep, so the second call sees .locked() and fast-fails.
    first = asyncio.create_task(scanner.async_request_active_window(3600.0))
    # Wait until the first task has run the entry set_mode call;
    # next line in the worker is the asyncio.sleep that holds the lock.
    while mock_client.bluetooth_scanner_set_mode.call_count == 0:
        await asyncio.sleep(0)
    assert await scanner.async_request_active_window(0.0) is False
    # Only the first task has called bluetooth_scanner_set_mode (the entry flip).
    assert mock_client.bluetooth_scanner_set_mode.call_count == 1
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first


@pytest.mark.asyncio
async def test_async_request_active_window_restore_runs_under_cancellation(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """Cancelling the task during the window still fires the restore call."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    task = asyncio.create_task(scanner.async_request_active_window(3600.0))
    # Wait until the entry call has fired (worker is now inside the
    # asyncio.sleep) so the cancel hits the sleep rather than racing
    # with the entry call's set_mode.
    while mock_client.bluetooth_scanner_set_mode.call_count == 0:
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    calls = [c.args for c in mock_client.bluetooth_scanner_set_mode.call_args_list]
    assert calls == [(BluetoothScannerMode.ACTIVE,), (BluetoothScannerMode.PASSIVE,)]


def test_scanner_tracks_configured_mode(scanner: ESPHomeScanner) -> None:
    """configured_mode mirrors state.configured_mode from the proxy."""
    assert scanner.configured_mode is None
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
            configured_mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert scanner.configured_mode == BluetoothScanningMode.PASSIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.ACTIVE,
            configured_mode=BluetoothScannerMode.ACTIVE,
        )
    )
    assert scanner.configured_mode == BluetoothScanningMode.ACTIVE


@pytest.mark.parametrize(
    ("intent", "expected_firmware_mode"),
    [
        (BluetoothScanningMode.ACTIVE, BluetoothScannerMode.ACTIVE),
        (BluetoothScanningMode.PASSIVE, BluetoothScannerMode.PASSIVE),
        (BluetoothScanningMode.AUTO, BluetoothScannerMode.PASSIVE),
    ],
)
def test_async_set_scanning_mode_sends_firmware_command(
    scanner: ESPHomeScanner,
    mock_client: APIClient,
    intent: BluetoothScanningMode,
    expected_firmware_mode: BluetoothScannerMode,
) -> None:
    """ACTIVE and PASSIVE pass through; AUTO maps to PASSIVE on the firmware."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    scanner.async_set_scanning_mode(intent)
    assert scanner.requested_mode == intent
    mock_client.bluetooth_scanner_set_mode.assert_called_once_with(
        expected_firmware_mode
    )


def test_async_set_scanning_mode_no_client_no_command(
    scanner: ESPHomeScanner,
) -> None:
    """Without a client the intent is stored but no firmware call is made."""
    scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)
    assert scanner.requested_mode == BluetoothScanningMode.AUTO


def test_async_set_scanning_mode_skips_when_firmware_already_matches(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """No wire traffic if the firmware is already configured for the target mode."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
            configured_mode=BluetoothScannerMode.PASSIVE,
        )
    )
    # AUTO -> firmware PASSIVE, which the proxy is already in.
    scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)
    mock_client.bluetooth_scanner_set_mode.assert_not_called()
    # Switching to ACTIVE still sends the command.
    scanner.async_set_scanning_mode(BluetoothScanningMode.ACTIVE)
    mock_client.bluetooth_scanner_set_mode.assert_called_once_with(
        BluetoothScannerMode.ACTIVE
    )


def test_async_set_scanning_mode_swallows_api_error(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """An APIConnectionError during firmware set is logged, intent still applied."""
    mock_client.bluetooth_scanner_set_mode = MagicMock(
        side_effect=APIConnectionError("boom")
    )
    scanner.set_client(mock_client)
    scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)
    assert scanner.requested_mode == BluetoothScanningMode.AUTO


def test_intent_pins_requested_mode_across_state_updates(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """After async_set_scanning_mode(AUTO), firmware state changes don't lower it."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
            configured_mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert scanner.requested_mode == BluetoothScanningMode.AUTO
    assert scanner.current_mode == BluetoothScanningMode.PASSIVE
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.ACTIVE,
            configured_mode=BluetoothScannerMode.PASSIVE,
        )
    )
    assert scanner.requested_mode == BluetoothScanningMode.AUTO
    assert scanner.current_mode == BluetoothScanningMode.ACTIVE


@pytest.mark.asyncio
async def test_active_window_restore_uses_intent(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """In AUTO the active window restores to PASSIVE even if current_mode flipped."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)
    mock_client.bluetooth_scanner_set_mode.reset_mock()
    assert await scanner.async_request_active_window(0.0) is True
    calls = [c.args for c in mock_client.bluetooth_scanner_set_mode.call_args_list]
    assert calls == [(BluetoothScannerMode.ACTIVE,), (BluetoothScannerMode.PASSIVE,)]


def test_restore_configured_mode_replays_original(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """The original configured_mode is restored after the integration changed it."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    # First observation: proxy was configured ACTIVE.
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.ACTIVE,
            configured_mode=BluetoothScannerMode.ACTIVE,
        )
    )
    # HA switches the integration to AUTO; firmware now reports configured_mode=PASSIVE.
    scanner.async_set_scanning_mode(BluetoothScanningMode.AUTO)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
            configured_mode=BluetoothScannerMode.PASSIVE,
        )
    )
    mock_client.bluetooth_scanner_set_mode.reset_mock()
    scanner.async_restore_configured_mode()
    mock_client.bluetooth_scanner_set_mode.assert_called_once_with(
        BluetoothScannerMode.ACTIVE
    )


def test_restore_configured_mode_no_observation_is_noop(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """If we never observed a configured_mode there is nothing to restore."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    scanner.async_restore_configured_mode()
    mock_client.bluetooth_scanner_set_mode.assert_not_called()


def test_restore_configured_mode_skips_when_already_matches(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """No wire traffic if the proxy is already in the original configured mode."""
    mock_client.bluetooth_scanner_set_mode = MagicMock()
    scanner.set_client(mock_client)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
            configured_mode=BluetoothScannerMode.PASSIVE,
        )
    )
    scanner.async_restore_configured_mode()
    mock_client.bluetooth_scanner_set_mode.assert_not_called()


def test_restore_configured_mode_no_client_is_noop(
    scanner: ESPHomeScanner,
) -> None:
    """No-op when there is no bound API client."""
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.ACTIVE,
            configured_mode=BluetoothScannerMode.ACTIVE,
        )
    )
    scanner.async_restore_configured_mode()


def test_restore_configured_mode_swallows_api_error(
    scanner: ESPHomeScanner, mock_client: APIClient
) -> None:
    """An APIConnectionError on the restore path is logged, not raised."""
    mock_client.bluetooth_scanner_set_mode = MagicMock(
        side_effect=APIConnectionError("boom")
    )
    scanner.set_client(mock_client)
    scanner.async_update_scanner_state(
        BluetoothScannerStateResponse(
            state=BluetoothScannerState.RUNNING,
            mode=BluetoothScannerMode.PASSIVE,
            configured_mode=BluetoothScannerMode.PASSIVE,
        )
    )
    scanner.async_restore_configured_mode()
