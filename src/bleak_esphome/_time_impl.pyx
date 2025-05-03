import cython

from posix.time cimport clock_gettime, timespec, CLOCK_MONOTONIC


cpdef double _monotonic_time_coarse():
    cdef timespec ts
    cdef double current
    clock_gettime(6, &ts)
    current = ts.tv_sec + (ts.tv_nsec / 1000000000.)
    return current

cpdef double _monotonic_time():
    cdef timespec ts
    cdef double current
    clock_gettime(CLOCK_MONOTONIC, &ts)
    current = ts.tv_sec + (ts.tv_nsec / 1000000000.)
    return current
