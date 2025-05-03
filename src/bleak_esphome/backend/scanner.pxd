


from ..time import USE_COARSE_MONOTONIC_TIME

if USE_COARSE_MONOTONIC_TIME:
    from .._time_impl cimport _monotonic_time_coarse as MONOTONIC_TIME
else:
    from .._time_impl cimport _monotonic_time as MONOTONIC_TIME


cdef object MONOTONIC_TIME
cdef object int_to_bluetooth_address
cdef object parse_advertisement_data_tuple
