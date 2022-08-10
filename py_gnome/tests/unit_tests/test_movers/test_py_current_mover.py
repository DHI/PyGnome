'''
Test all operations for py_current mover work
'''




import datetime
import os
from os.path import basename

import numpy as np
import pytest
import tempfile
import zipfile

from gnome.movers import PyCurrentMover
from gnome.utilities import time_utils

from ..conftest import (sample_sc_release,
                        testdata,
                        validate_serialize_json,
                        validate_save_json)


curr_file = testdata['c_GridCurrentMover']['curr_reg'] #just a regular grid netcdf - this fails save_load
curr_file2 = testdata['c_GridCurrentMover']['curr_tri'] #a triangular grid netcdf


def test_exceptions():
    """
    Test correct exceptions are raised
    """

    #bad_file = os.path.join('./', 'tidesWAC.CURX')
    #bad_file = None
    with pytest.raises(ValueError):
        PyCurrentMover()


num_le = 10
start_pos = (3.549, 51.88, 0)
rel_time = datetime.datetime(1999, 11, 29, 21)
#rel_time = datetime.datetime(2004, 12, 31, 13)	# date for curr_file2
time_step = 15 * 60  # seconds
model_time = time_utils.sec_to_date(time_utils.date_to_sec(rel_time))


def test_loop():
    """
    test one time step with no uncertainty on the spill
    checks there is non-zero motion.
    also checks the motion is same for all LEs
    """

    pSpill = sample_sc_release(num_le, start_pos, rel_time)
    py_current = PyCurrentMover(curr_file)
    delta = _certain_loop(pSpill, py_current)

    _assert_move(delta)

    assert np.all(delta[:, 0] == delta[0, 0])  # lat move matches for all LEs
    assert np.all(delta[:, 1] == delta[0, 1])  # long move matches for all LEs
    assert np.all(delta[:, 2] == 0)  # 'z' is zeros

    return delta


def test_uncertain_loop():
    """
    test one time step with uncertainty on the spill
    checks there is non-zero motion.
    """

    pSpill = sample_sc_release(num_le, start_pos, rel_time,
                               uncertain=True)
    py_current = PyCurrentMover(curr_file)
    u_delta = _uncertain_loop(pSpill, py_current)

    _assert_move(u_delta)

    return u_delta


def test_certain_uncertain():
    """
    make sure certain and uncertain loop results in different deltas
    """

    delta = test_loop()
    u_delta = test_uncertain_loop()
    print()
    print(delta)
    print(u_delta)
    assert np.all(delta[:, :2] != u_delta[:, :2])
    assert np.all(delta[:, 2] == u_delta[:, 2])


py_cur = PyCurrentMover(curr_file)


def test_default_props():
    """
    test default properties
    """
    assert py_cur.uncertain_duration == 24 * 3600
    assert py_cur.uncertain_time_delay == 0
    assert py_cur.uncertain_along == 0.5
    assert py_cur.uncertain_cross == 0.25
    assert py_cur.scale_value == 1
    #assert py_cur.time_offset == 0
    assert py_cur.default_num_method == 'RK2'
    #assert py_cur.grid_topology == None


def test_scale_value():
    """
    test setting / getting properties
    """

    py_cur.scale_value = 0
    print(py_cur.scale_value)
    assert py_cur.scale_value == 0


# Helper functions for tests

def _assert_move(delta):
    """
    helper function to test assertions
    """

    print()
    print(delta)
    assert np.all(delta[:, :2] != 0)
    assert np.all(delta[:, 2] == 0)


def _certain_loop(pSpill, py_current):
    py_current.prepare_for_model_run()
    py_current.prepare_for_model_step(pSpill, time_step, model_time)
    delta = py_current.get_move(pSpill, time_step, model_time)
    py_current.model_step_is_done(pSpill)

    return delta


def _uncertain_loop(pSpill, py_current):
    py_current.prepare_for_model_run()
    py_current.prepare_for_model_step(pSpill, time_step, model_time)
    u_delta = py_current.get_move(pSpill, time_step, model_time)
    py_current.model_step_is_done(pSpill)

    return u_delta


def test_serialize_deserialize():
    """
    test serialize/deserialize/update_from_dict doesn't raise errors
    """
    py_current = PyCurrentMover(curr_file2)

    serial = py_current.serialize()
    assert validate_serialize_json(serial, py_current)

    # check our PyCurrentMover attributes

    deser = PyCurrentMover.deserialize(serial)

    assert deser == py_current


def test_save_load():
    """
    test save/loading
    """

    saveloc = tempfile.mkdtemp()
    py_current = PyCurrentMover(curr_file2)
    save_json, zipfile_, _refs = py_current.save(saveloc)

    assert validate_save_json(save_json, zipfile.ZipFile(zipfile_), py_current)

    loaded = PyCurrentMover.load(zipfile_)

    assert loaded == py_current