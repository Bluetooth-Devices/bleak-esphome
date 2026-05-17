"""Tests for the top-level ``bleak_esphome`` package surface."""

from __future__ import annotations

import bleak_esphome
from bleak_esphome import (
    APIConnectionManager,
    ESPHomeDeviceConfig,
    ESPHomeStartAborted,
    connect_scanner,
)
from bleak_esphome.connect import connect_scanner as _connect_scanner_impl
from bleak_esphome.connection_manager import (
    APIConnectionManager as _APIConnectionManager_impl,
)
from bleak_esphome.connection_manager import (
    ESPHomeDeviceConfig as _ESPHomeDeviceConfig_impl,
)
from bleak_esphome.connection_manager import (
    ESPHomeStartAborted as _ESPHomeStartAborted_impl,
)


def test_public_all_matches_module_exports() -> None:
    """``__all__`` must list exactly the names re-exported at package root."""
    assert set(bleak_esphome.__all__) == {
        "APIConnectionManager",
        "ESPHomeDeviceConfig",
        "ESPHomeStartAborted",
        "connect_scanner",
    }
    for name in bleak_esphome.__all__:
        assert hasattr(bleak_esphome, name), name


def test_public_reexports_resolve_to_canonical_objects() -> None:
    """Re-exports must be the same objects as their canonical definitions."""
    assert connect_scanner is _connect_scanner_impl
    assert APIConnectionManager is _APIConnectionManager_impl
    assert ESPHomeDeviceConfig is _ESPHomeDeviceConfig_impl
    assert ESPHomeStartAborted is _ESPHomeStartAborted_impl


def test_esphome_start_aborted_is_exception_subclass() -> None:
    """``ESPHomeStartAborted`` must be raisable and inherit from ``Exception``."""
    assert issubclass(ESPHomeStartAborted, Exception)
    err = ESPHomeStartAborted("aborted")
    assert str(err) == "aborted"
