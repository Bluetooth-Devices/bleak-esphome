"""Tests for the spurious-cancellation helper."""

from __future__ import annotations

import asyncio

import pytest

from bleak_esphome._cancellation import is_spurious_cancellation


@pytest.mark.asyncio
async def test_returns_true_when_not_externally_cancelled() -> None:
    """Inside a normal task with no pending cancel, the helper returns True."""
    assert is_spurious_cancellation() is True


@pytest.mark.asyncio
async def test_returns_false_when_task_was_cancelled() -> None:
    """After ``task.cancel()`` raises, ``cancelling()`` is >= 1."""
    saw_external: list[bool] = []

    async def victim() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            saw_external.append(is_spurious_cancellation())
            raise

    task = asyncio.create_task(victim())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert saw_external == [False]


@pytest.mark.asyncio
async def test_returns_true_when_inner_future_was_cancelled() -> None:
    """A future cancelled from inside the task does not bump ``cancelling()``."""
    saw_spurious: list[bool] = []
    loop = asyncio.get_running_loop()

    async def runner() -> None:
        fut: asyncio.Future[None] = loop.create_future()
        loop.call_soon(fut.cancel)
        try:
            await fut
        except asyncio.CancelledError:
            saw_spurious.append(is_spurious_cancellation())
            raise

    with pytest.raises(asyncio.CancelledError):
        await asyncio.shield(asyncio.create_task(runner()))

    assert saw_spurious == [True]


@pytest.mark.asyncio
async def test_returns_true_when_called_from_callback() -> None:
    """Inside a loop callback there is no current task — should be True."""
    loop = asyncio.get_running_loop()
    result: list[bool] = []
    done = loop.create_future()

    def callback() -> None:
        result.append(is_spurious_cancellation())
        done.set_result(None)

    loop.call_soon(callback)
    await done
    assert result == [True]
