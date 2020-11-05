#!/usr/bin/env python

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import numpy as np

from gnome.utilities.transforms import r_theta_to_uv_wind, \
    uv_to_r_theta_wind, r_theta_to_uv_current, uv_to_r_theta_current

import pytest


# use test fixtures invalid_rq, rq_wind and wind_rand
# Defined in conftest.py

def test_exceptions(invalid_rq):
    with pytest.raises(ValueError):
        r_theta_to_uv_wind(invalid_rq['rq'][0])
    with pytest.raises(ValueError):
        r_theta_to_uv_wind(invalid_rq['rq'][1])
    with pytest.raises(ValueError):
        r_theta_to_uv_wind(invalid_rq['rq'][2])


atol = 1e-14
rtol = 0

# randomly generate (r,theta), apply transform + inverse
# and check result is within 1e-10

inv_atol = 1e-10


def test_r_theta_to_uv_wind(rq_wind):
    uv_out = r_theta_to_uv_wind(rq_wind['rq'])
    print('actual (u,v): ')
    print(uv_out)
    print('computed (u,v): ')
    print(rq_wind['uv'])
    assert np.allclose(uv_out, rq_wind['uv'], atol, rtol)


def test_uv_to_r_theta_wind(rq_wind):
    rq_out = uv_to_r_theta_wind(rq_wind['uv'])
    print('actual (r,theta): ')
    print(rq_out)
    print('computed (r,theta): ')
    print(rq_wind['rq'])
    assert np.allclose(rq_out, rq_wind['rq'], atol, rtol)


def test_wind_inverse(rq_rand):
    """
    randomly generates an (r,theta) and applies the transform to
    convert to (u,v), then back to (r,theta).
    It checks the result is accurate to within 10-10 absolute tolerance
    """

    rq_out = uv_to_r_theta_wind(r_theta_to_uv_wind(rq_rand['rq']))
    print('actual (r,theta): ')
    print(rq_rand['rq'])
    print('computed (r,theta): ')
    print(rq_out)
    assert np.allclose(rq_out, rq_rand['rq'], inv_atol, rtol)


def test_r_theta_to_uv_current(rq_curr):
    uv_out = r_theta_to_uv_current(rq_curr['rq'])
    assert np.allclose(uv_out, rq_curr['uv'], atol, rtol)


def test_uv_to_r_theta_current(rq_curr):
    rq_out = uv_to_r_theta_current(rq_curr['uv'])
    assert np.allclose(rq_out, rq_curr['rq'], atol, rtol)


def test_current_inverse(rq_rand):
    """
    randomly generates an (r,theta) and applies the transform to
    convert to (u,v), then back to (r,theta).
    It checks the result is accurate to within 10-10 tolerance
    """

    rq_out = uv_to_r_theta_current(r_theta_to_uv_current(rq_rand['rq']))
    print('actual (r,theta): ')
    print(rq_rand['rq'])
    print('computed (r,theta): ')
    print(rq_out)
    assert np.allclose(rq_out, rq_rand['rq'], inv_atol, rtol)


