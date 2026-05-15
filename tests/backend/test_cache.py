"""Tests for ESPHomeBluetoothCache."""

from __future__ import annotations

from bleak.backends.service import BleakGATTServiceCollection

from bleak_esphome.backend.cache import MAX_CACHED_SERVICES, ESPHomeBluetoothCache


def test_get_gatt_services_cache_miss_returns_none() -> None:
    """An unknown address yields ``None`` rather than raising."""
    cache = ESPHomeBluetoothCache()
    assert cache.get_gatt_services_cache(0xAABBCCDDEEFF) is None


def test_set_and_get_gatt_services_cache_round_trips() -> None:
    """A stored ``BleakGATTServiceCollection`` comes back unchanged."""
    cache = ESPHomeBluetoothCache()
    services = BleakGATTServiceCollection()
    cache.set_gatt_services_cache(1, services)
    assert cache.get_gatt_services_cache(1) is services


def test_clear_gatt_services_cache_removes_entry() -> None:
    """Clearing an existing entry evicts it from the cache."""
    cache = ESPHomeBluetoothCache()
    services = BleakGATTServiceCollection()
    cache.set_gatt_services_cache(1, services)
    cache.clear_gatt_services_cache(1)
    assert cache.get_gatt_services_cache(1) is None


def test_clear_gatt_services_cache_missing_key_is_noop() -> None:
    """Clearing an absent entry must not raise."""
    cache = ESPHomeBluetoothCache()
    cache.clear_gatt_services_cache(0xDEADBEEF)


def test_get_gatt_mtu_cache_miss_returns_none() -> None:
    """An unknown address yields ``None`` rather than raising."""
    cache = ESPHomeBluetoothCache()
    assert cache.get_gatt_mtu_cache(0xAABBCCDDEEFF) is None


def test_set_and_get_gatt_mtu_cache_round_trips() -> None:
    """A stored MTU value comes back unchanged."""
    cache = ESPHomeBluetoothCache()
    cache.set_gatt_mtu_cache(1, 247)
    assert cache.get_gatt_mtu_cache(1) == 247


def test_clear_gatt_mtu_cache_removes_entry() -> None:
    """Clearing an existing MTU evicts it from the cache."""
    cache = ESPHomeBluetoothCache()
    cache.set_gatt_mtu_cache(1, 247)
    cache.clear_gatt_mtu_cache(1)
    assert cache.get_gatt_mtu_cache(1) is None


def test_clear_gatt_mtu_cache_missing_key_is_noop() -> None:
    """Clearing an absent MTU must not raise."""
    cache = ESPHomeBluetoothCache()
    cache.clear_gatt_mtu_cache(0xDEADBEEF)


def test_services_and_mtu_caches_are_independent() -> None:
    """Updating one cache does not affect the other for the same key."""
    cache = ESPHomeBluetoothCache()
    services = BleakGATTServiceCollection()
    cache.set_gatt_services_cache(1, services)
    cache.set_gatt_mtu_cache(1, 185)
    cache.clear_gatt_services_cache(1)
    assert cache.get_gatt_services_cache(1) is None
    assert cache.get_gatt_mtu_cache(1) == 185
    cache.clear_gatt_mtu_cache(1)
    cache.set_gatt_services_cache(1, services)
    assert cache.get_gatt_services_cache(1) is services
    assert cache.get_gatt_mtu_cache(1) is None


def test_services_cache_evicts_least_recently_used_past_capacity() -> None:
    """Inserting past ``MAX_CACHED_SERVICES`` evicts the LRU entry."""
    cache = ESPHomeBluetoothCache()
    collections = [BleakGATTServiceCollection() for _ in range(MAX_CACHED_SERVICES)]
    for idx, services in enumerate(collections):
        cache.set_gatt_services_cache(idx, services)
    # All present.
    assert cache.get_gatt_services_cache(0) is collections[0]
    assert cache.get_gatt_services_cache(MAX_CACHED_SERVICES - 1) is collections[-1]
    # Touch entry 0 so 1 becomes the LRU.
    cache.get_gatt_services_cache(0)
    overflow = BleakGATTServiceCollection()
    cache.set_gatt_services_cache(MAX_CACHED_SERVICES, overflow)
    assert cache.get_gatt_services_cache(MAX_CACHED_SERVICES) is overflow
    assert cache.get_gatt_services_cache(1) is None
    assert cache.get_gatt_services_cache(0) is collections[0]


def test_mtu_cache_evicts_least_recently_used_past_capacity() -> None:
    """Inserting past ``MAX_CACHED_SERVICES`` evicts the LRU MTU entry."""
    cache = ESPHomeBluetoothCache()
    for idx in range(MAX_CACHED_SERVICES):
        cache.set_gatt_mtu_cache(idx, 100 + idx)
    assert cache.get_gatt_mtu_cache(0) == 100
    cache.get_gatt_mtu_cache(0)
    cache.set_gatt_mtu_cache(MAX_CACHED_SERVICES, 999)
    assert cache.get_gatt_mtu_cache(MAX_CACHED_SERVICES) == 999
    assert cache.get_gatt_mtu_cache(1) is None
    assert cache.get_gatt_mtu_cache(0) == 100


def test_distinct_instances_have_isolated_state() -> None:
    """Two cache instances do not share their LRU mappings."""
    cache_a = ESPHomeBluetoothCache()
    cache_b = ESPHomeBluetoothCache()
    services = BleakGATTServiceCollection()
    cache_a.set_gatt_services_cache(1, services)
    cache_a.set_gatt_mtu_cache(1, 247)
    assert cache_b.get_gatt_services_cache(1) is None
    assert cache_b.get_gatt_mtu_cache(1) is None
