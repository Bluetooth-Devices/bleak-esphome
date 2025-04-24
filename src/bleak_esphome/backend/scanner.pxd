
from habluetooth.base_scanner cimport BaseHaRemoteScanner

cdef object MONOTONIC_TIME
cdef object int_to_bluetooth_address
cdef object parse_advertisement_data_tuple



cdef object BLEResponse_advertisements
cdef object BLE_address
cdef object BLE_data
cdef object BLE_rssi
cdef object BLE_address_type


cdef class ESPHomeScanner(BaseHaRemoteScanner):
    pass
