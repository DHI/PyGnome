"""
cy_shio_time.pyx module declaration file
Used to share members of the CyShioTime class
This file must have the same name as the pyx file, but with a pxd suffix
"""

from .utils cimport ShioTimeValue_c
from .cy_ossm_time cimport CyOSSMTime

cdef class CyShioTime(CyOSSMTime):
    cdef ShioTimeValue_c * shio
    cdef unicode _yeardata_path
