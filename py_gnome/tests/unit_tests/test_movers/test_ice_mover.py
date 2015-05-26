'''
Test all operations for ice mover work
'''

import datetime
import os

import numpy as np
import pytest

from gnome.movers import IceMover, GridCurrentMover
from gnome.utilities import time_utils

from ..conftest import sample_sc_release, testdata

ice_file = testdata['IceMover']['ice_curr_curv']
topology_file = testdata['IceMover']['ice_top_curv']


# def test_exceptions():
#     """
#     Test correct exceptions are raised
#     """
#     with pytest.raises(ValueError):
#         # file does not exist
#         IceMover(os.path.join('./', 'ChesBay.CUR'))
# 
#     with pytest.raises(OSError):
#         IceMover(testdata['CurrentCycleMover']['curr_bad_file'])
# 
#     with pytest.raises(TypeError):
#         IceMover(curr_file, topology_file=10)
# 

num_le = 4
start_pos = (-164.01696, 72.921024, 0)
rel_time = datetime.datetime(2015, 5, 14, 0)
time_step = 15 * 60  # seconds
test_time = time_utils.date_to_sec(rel_time)
model_time = time_utils.sec_to_date(time_utils.date_to_sec(rel_time))


def test_loop():
    """
    test one time step with no uncertainty on the spill
    checks there is non-zero motion.
    also checks the motion is same for all LEs
    """

    pSpill = sample_sc_release(num_le, start_pos, rel_time)
    ice_mover = IceMover(ice_file, topology_file)
    delta = _certain_loop(pSpill, ice_mover)

    _assert_move(delta)

    assert np.all(delta[:, 0] == delta[0, 0])  # lat move matches for all LEs
    assert np.all(delta[:, 1] == delta[0, 1])  # long move matches for all LEs
    assert np.all(delta[:, 2] == 0)  # 'z' is zeros

    return delta

def test_loop_gridcurrent():
    """
    test one time step with no uncertainty on the spill
    checks there is non-zero motion.
    also checks the motion is same for all LEs
    """

    pSpill = sample_sc_release(num_le, start_pos, rel_time)
    curr = GridCurrentMover(ice_file, topology_file)
    delta = _certain_loop(pSpill, curr)

    _assert_move(delta)

    assert np.all(delta[:, 0] == delta[0, 0])  # lat move matches for all LEs
    assert np.all(delta[:, 1] == delta[0, 1])  # long move matches for all LEs
    assert np.all(delta[:, 2] == 0)  # 'z' is zeros

    return delta

def test_ice_fields():
    """
    test one time step with no uncertainty on the spill
    checks there is non-zero motion.
    also checks the motion is same for all LEs
    """

    pSpill = sample_sc_release(num_le, start_pos, rel_time)
    ice_mover = IceMover(ice_file, topology_file)
    vels = ice_mover.get_ice_velocities(test_time)
    frac, thick = ice_mover.get_ice_fields(test_time)

    assert (np.all(frac[:] <= 1) and np.all(frac[:] >= 0)) # fraction values between 0 and 1
    assert (np.all(thick[:] <= 10) and np.all(thick[:] >= 0)) # thickness >=0, < 10 in this example...

    #return frac, thick


# def test_uncertain_loop(uncertain_time_delay=0):
#     """
#     test one time step with uncertainty on the spill
#     checks there is non-zero motion.
#     """
# 
#     pSpill = sample_sc_release(num_le, start_pos, rel_time,
#                                uncertain=True)
#     curr = IceMover(curr_file, topology_file)
#     curr.uncertain_time_delay=uncertain_time_delay
#     u_delta = _uncertain_loop(pSpill, curr)
# 
#     _assert_move(u_delta)
# 
#     return u_delta
# 
# 
# def test_certain_uncertain():
#     """
#     make sure certain and uncertain loop results in different deltas
#     """
# 
#     delta = test_loop()
#     u_delta = test_uncertain_loop()
#     print
#     print delta
#     print u_delta
#     assert np.all(delta[:, :2] != u_delta[:, :2])
#     assert np.all(delta[:, 2] == u_delta[:, 2])
#     uncertain_time_delay = 3
#     u_delta = test_uncertain_loop(uncertain_time_delay)
#     print u_delta
#     assert np.all(delta[:, :2] == u_delta[:, :2])
# 

c_grid = IceMover(ice_file,topology_file)


# def test_default_props():
#     """
#     test default properties
#     """
# 
#     assert c_grid.current_scale == 1
#     assert c_grid.uncertain_time_delay == 0
#     assert c_grid.uncertain_duration == 24
#     assert c_grid.uncertain_cross == .25
#     assert c_grid.uncertain_along == .5
#     assert c_grid.extrapolate == False
#     assert c_grid.time_offset == 0
# 

# def test_scale():
#     """
#     test setting / getting properties
#     """
# 
#     c_grid.uncertain_time_delay = 3
#     assert c_grid.uncertain_time_delay == 3
# 
# 
# def test_scale_value():
#     """
#     test setting / getting properties
#     """
# 
#     c_grid.current_scale = 2
#     print c_grid.current_scale
#     assert c_grid.current_scale == 2
# 
# 
# def test_extrapolate():
#     """
#     test setting / getting properties
#     """
# 
#     c_grid.extrapolate = True
#     print c_grid.extrapolate
#     assert c_grid.extrapolate == True
# 
# 
# def test_offset_time():
#     """
#     test setting / getting properties
#     """
# 
#     c_grid.time_offset = -8
#     print c_grid.time_offset
#     assert c_grid.time_offset == -8
# 
# 
# Helper functions for tests

def _assert_move(delta):
    """
    helper function to test assertions
    """

    print
    print delta
    assert np.all(delta[:, :2] != 0)
    assert np.all(delta[:, 2] == 0)


def _certain_loop(pSpill, mover):
    mover.prepare_for_model_run()
    mover.prepare_for_model_step(pSpill, time_step, model_time)
    delta = mover.get_move(pSpill, time_step, model_time)
    mover.model_step_is_done()

    return delta


def _uncertain_loop(pSpill, mover):
    mover.prepare_for_model_run()
    mover.prepare_for_model_step(pSpill, time_step, model_time)
    u_delta = mover.get_move(pSpill, time_step, model_time)
    mover.model_step_is_done()

    return u_delta


# def test_serialize_deserialize():
#     """
#     test to_dict function for Ice object
#     create a new ice object and make sure it has same properties
#     """
# 
#     c_grid = IceMover(curr_file, topology_file)
#     serial = c_grid.serialize('webapi')
#     dict_ = IceMover.deserialize(serial)
#     c2 = IceMover.new_from_dict(dict_)
#     assert c_grid == c2
# 
#     c_grid.update_from_dict(dict_)  # tests no failures
# 
