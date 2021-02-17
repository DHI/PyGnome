#!/usr/bin/env python

"""
unit tests for the memory use check

not sure how to test for real, but at least this tells you that you can call them...

designed to be run with py.test
"""
from __future__ import division
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import pytest

from gnome.utilities import get_mem_use


def test_mem_use():
    """
    can we call it?
    """
    val_KB = get_mem_use('KB')
    val_MB = get_mem_use()
    val_GB = get_mem_use('GB')

    assert val_MB == val_KB / 1024

    assert val_GB == val_KB / 1024 / 1024


@pytest.mark.xfail
def test_increase():
    """
    does it go up when you allocate objects?

    Note: this may not pass if the python process has a bunch of spare memory
    allocated already..

    todo: make this test better, it doesn't always pass. The memory usage does
    not always increase.
    """
    import array
    start = get_mem_use()
    l = [array.array('b', b'some bytes'*1024) for i in range(10000)]

    assert get_mem_use() > start