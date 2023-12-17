"""Bluetooth support for esphome."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from functools import partial
from typing import TYPE_CHECKING, Any, Callable

from aioesphomeapi import APIClient, BluetoothProxyFeature, DeviceInfo
from habluetooth import (
    HaBluetoothConnector,
)

from .backend.cache import ESPHomeBluetoothCache
from .backend.client import ESPHomeClient, ESPHomeClientData
from .backend.device import ESPHomeBluetoothDevice
from .backend.scanner import ESPHomeScanner

_LOGGER = logging.getLogger(__name__)


def _can_connect(bluetooth_device: ESPHomeBluetoothDevice, source: str) -> bool:
    """Check if a given source can make another connection."""
    can_connect = bool(
        bluetooth_device.available and bluetooth_device.ble_connections_free
    )
    _LOGGER.debug(
        (
            "%s [%s]: Checking can connect, available=%s, ble_connections_free=%s"
            " result=%s"
        ),
        bluetooth_device.name,
        source,
        bluetooth_device.available,
        bluetooth_device.ble_connections_free,
        can_connect,
    )
    return can_connect


async def connect_scanner(
    cli: APIClient,
    device_info: DeviceInfo,
    cache: ESPHomeBluetoothCache,
    available: bool,
) -> ESPHomeClientData:
    """
    Connect scanner.

    The caller is responsible for:

    1. Calling ESPHomeClientData.scanner.async_setup()
    2. Calling ESPHomeClientData.disconnect_callbacks when the ESP is disconnected.
    3. Registering the scanner with the HA Bluetooth manager and also
       un-registering it when the ESP is disconnected.

    The caller may choose to override ESPHomeClientData.disconnect_callbacks
    with its own set. If it does so, it must do so before calling
    ESPHomeClientData.scanner.async_setup().
    """
    source = device_info.mac_address
    name = device_info.name
    if TYPE_CHECKING:
        assert cli.api_version is not None
    feature_flags = device_info.bluetooth_proxy_feature_flags_compat(cli.api_version)
    connectable = bool(feature_flags & BluetoothProxyFeature.ACTIVE_CONNECTIONS)
    bluetooth_device = ESPHomeBluetoothDevice(
        name, device_info.mac_address, available=available
    )
    _LOGGER.debug(
        "%s [%s]: Connecting scanner feature_flags=%s, connectable=%s",
        name,
        source,
        feature_flags,
        connectable,
    )
    client_data = ESPHomeClientData(
        bluetooth_device=bluetooth_device,
        cache=cache,
        client=cli,
        device_info=device_info,
        api_version=cli.api_version,
        title=name,
        scanner=None,
    )
    connector = HaBluetoothConnector(
        client=partial(ESPHomeClient, client_data=client_data),
        source=source,
        can_connect=partial(_can_connect, bluetooth_device, source),
    )
    scanner = ESPHomeScanner(source, name, connector, connectable)
    client_data.scanner = scanner
    coros: list[Coroutine[Any, Any, Callable[[], None]]] = []
    # These calls all return a callback that can be used to unsubscribe
    # but we never unsubscribe so we don't care about the return value

    if connectable:
        # If its connectable be sure not to register the scanner
        # until we know the connection is fully setup since otherwise
        # there is a race condition where the connection can fail
        coros.append(
            cli.subscribe_bluetooth_connections_free(
                bluetooth_device.async_update_ble_connection_limits
            )
        )

    if feature_flags & BluetoothProxyFeature.RAW_ADVERTISEMENTS:
        coros.append(
            cli.subscribe_bluetooth_le_raw_advertisements(
                scanner.async_on_raw_advertisements
            )
        )
    else:
        coros.append(
            cli.subscribe_bluetooth_le_advertisements(scanner.async_on_advertisement)
        )

    await asyncio.gather(*coros)
    return client_data
