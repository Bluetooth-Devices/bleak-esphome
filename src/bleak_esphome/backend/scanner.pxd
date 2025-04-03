
from habluetooth.base_scanner cimport BaseHaRemoteScanner

cdef object MONOTONIC_TIME
cdef object int_to_bluetooth_address
cdef object parse_advertisement_data_tuple

cdef class ESPHomeScanner(BaseHaRemoteScanner):
    pass
