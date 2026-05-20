"""Helpers for distinguishing externally-cancelled tasks from internal ones."""

from __future__ import annotations

import asyncio


def is_spurious_cancellation() -> bool:
    """
    Return True when ``CancelledError`` did not come from ``task.cancel()``.

    ``asyncio.Task.cancelling()`` returns the number of pending cancel
    requests on the running task. A count of ``0`` (or no current task at
    all) means the ``CancelledError`` was raised by something *inside* the
    task — usually a future being cancelled by another code path — rather
    than by an external caller cancelling the task itself.

    Callers typically use this to convert a spurious ``CancelledError``
    into a domain-specific exception so it does not leak as a cancellation
    that breaks ``TaskGroup`` or ``asyncio.timeout`` semantics for the
    caller above.
    """
    current_task = asyncio.current_task()
    return current_task is None or current_task.cancelling() == 0
