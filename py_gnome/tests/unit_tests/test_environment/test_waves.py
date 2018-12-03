#!/usr/bin/env python

"""
test code for the wave calculations
"""

import datetime
import numpy as np

from copy import copy

from gnome.environment import constant_wind
from gnome.environment import Waves
from gnome.environment import Water
from gnome.environment import Wind
from gnome.basic_types import datetime_value_2d
from gnome.exceptions import ReferencedObjectNotSet

import pytest

# some test setup
start_time = datetime.datetime(2014, 12, 1, 0)

# 10 m/s
series = np.array((start_time, (10, 45)),
                  dtype=datetime_value_2d).reshape((1, ))
test_wind_10 = Wind(timeseries=series, units='meter per second')

# 5 m/s
series = np.array((start_time, (5, 45)),
                  dtype=datetime_value_2d).reshape((1, ))
test_wind_5 = Wind(timeseries=series, units='meter per second')

# 3 m/s
series = np.array((start_time, (3, 45)),
                  dtype=datetime_value_2d).reshape((1, ))
test_wind_3 = Wind(timeseries=series, units='meter per second')

# 0 m/s
series = np.array((start_time, (0, 45)),
                  dtype=datetime_value_2d).reshape((1, ))
test_wind_0 = Wind(timeseries=series, units='meter per second')

# default water object
default_water = Water()


def test_init():
    w = Waves(test_wind_5, default_water)

    # just to assert something
    assert type(w) == Waves


def test_exception():
    w = Waves()

    # wind object undefined
    with pytest.raises(ReferencedObjectNotSet):
        w.prepare_for_model_run(start_time)

    w.wind = test_wind_0

    # water object undefined
    with pytest.raises(ReferencedObjectNotSet):
        w.prepare_for_model_run(start_time)


def test_compute_H():
    """can it compute a wave height at all?

       fetch unlimited
    """
    w = Waves(test_wind_5, default_water)
    H = w.compute_H(5)  # five m/s wind

    print H

    # I have no idea what the answers _should_ be
    # assert H == 0


def test_compute_H_fetch():
    """
        can it compute a wave height at all?
        fetch limited case
    """
    water = copy(default_water)
    water.fetch = 10000  # 10km

    w = Waves(test_wind_5, water)  # 10km
    H = w.compute_H(5)  # five m/s wind

    print H
    # assert H == 0


def test_compute_H_fetch_huge():
    """
    With a huge fetch, should be same as fetch-unlimited
    """
    water = copy(default_water)
    water.fetch = 1e100  # 10km

    w = Waves(test_wind_5, water)

    H_f = w.compute_H(5)  # five m/s wind
    w.fetch = None
    H_nf = w.compute_H(5)

    assert H_f == H_nf


@pytest.mark.parametrize("U", [1.0, 2.0, 4.0, 8.0, 16.0, 32.0])
def test_pseudo_wind(U):
    """
    should reverse the wave height computation
    at least for fetch-unlimited
    """
    w = Waves(test_wind_5, default_water)

    print "testing for U:", U
    # 0.707 compensates for RMS wave height
    assert round(w.pseudo_wind(w.compute_H(U) / 0.707), 5) == round(U, 8)


# note: 200 becuse that's when whitecap fraction would go above 1.0
@pytest.mark.parametrize("U", [0.0, 1.0, 2.0, 2.99, 3.0,
                               4.0, 8.0, 16.0, 32.0, 200.0])
def test_whitecap_fraction(U):
    """
    Fraction whitcapping -- doesn't really check values
    but should catch gross errors!
    """
    print "testing for U:", U

    w = Waves(test_wind_5, default_water)
    f = w.whitecap_fraction(U)

    assert f >= 0.0
    assert f <= 1.0

    if U == 4.0:
        # assert round(f, 8) == round(0.05 / 3.85, 8)
        # included the .5 factor from ADIOS2
        assert round(f, 8) == round(0.05 / 3.85 / 2, 8)


@pytest.mark.parametrize("U", [0.0, 1.0, 2.0, 3.0, 4.0, 8.0, 16.0, 32.0])
def test_mean_wave_period(U):
    """
    test the wave period
    """
    w = Waves(test_wind_5, default_water)

    print "testing for U:", U

    f = w.mean_wave_period(U)

    print f
    # assert False # what else to check for???


@pytest.mark.parametrize("U", [0.0, 1.0, 2.0, 3.0, 4.0, 8.0, 16.0, 32.0])
def test_mean_wave_period_with_fetch(U):
    """
    Test the wave period
    """
    print "testing for U:", U

    water = copy(default_water)
    water.fetch = 1e4  # 10km
    w = Waves(test_wind_5, water)  # 10km fetch

    T = w.mean_wave_period(U)

    print T
    # assert False # what else to check for???


@pytest.mark.parametrize("H, expected", [(0.0, 0.0),
                                         (1.0, 34.01),
                                         (2.0, 136.39),
                                         (4.0, 545.58),
                                         (8.0, 2182.35)])
def test_wave_energy(H, expected):
    """
    Test the dissipative wave energy
    """
    print "testing for H:", H

    water = copy(default_water)
    water.fetch = 1e4  # 10km
    w = Waves(test_wind_5, water)  # 10km fetch

    De = w.dissipative_wave_energy(H)

    print De

    # Note: Right now we are just documenting the results that we are
    #       getting.  The expected values need to be checked for validity.
    assert np.isclose(De, expected, rtol=0.01)


@pytest.mark.parametrize("wind_speed, expected", [(0.0, 0.0),
                                                  (1.0, 0.75),
                                                  (2.0, 1.5),
                                                  (4.0, 3.0),
                                                  (8.0, 6.0),
                                                  (16.0, 12.0)])
def test_peak_wave_period(wind_speed, expected):
    "fully developed seas"
    series = np.array((start_time, (wind_speed, 45)),
                      dtype=datetime_value_2d).reshape((1, ))
    test_wind = Wind(timeseries=series, units='meter per second')

    w = Waves(test_wind, default_water)

    print 'Wind speed:', w.wind.get_value(start_time)

    T_w = w.peak_wave_period(None, start_time)

    assert np.isclose(T_w, expected)


def test_call_no_fetch_or_height():
    "fully developed seas"
    w = Waves(test_wind_5, default_water)

    H, T, Wf, De = w.get_value(None, start_time)

    print H, T, Wf, De

    print "Need to check reasonable numbers"


def test_call_fetch():

    water = copy(default_water)
    water.fetch = 1e4  # 10km
    w = Waves(test_wind_5, water)

    H, T, Wf, De = w.get_value(None, start_time)

    print H, T, Wf, De

    print "Need to check reasonable numbers"


def test_call_height():
    """ call with specified wave height """

    water = copy(default_water)
    water.wave_height = 1.0
    w = Waves(test_wind_5, water)

    H, T, Wf, De = w.get_value(None, start_time)

    print H, T, Wf, De

    assert H == .707	# returns root mean square wave height
    # fixme: add some value checks -- what to use???


def test_serialize_deseriailize():
    'test serialize/deserialize for webapi'
    wind = constant_wind(1., 0)
    water = Water()
    w = Waves(wind, water)

    json_ = w.serialize()

    # deserialize and ensure the dict's are correct
    w2 = Waves.deserialize(json_)
    assert w2.wind == Wind.deserialize(json_['wind'])
    assert w2.water == Water.deserialize(json_['water'])
    assert w == w2

def test_get_emulsification_wind():
    wind = constant_wind(3., 0)
    water = Water()
    w = Waves(wind, water)

    print w.get_emulsification_wind(None, start_time)
    assert w.get_emulsification_wind(None, start_time) == 3.0


def test_get_emulsification_wind_with_wave_height():
    wind = constant_wind(3., 0)
    water = Water()
    water.wave_height = 2.0
    w = Waves(wind, water)

    print w.get_value(None, start_time)

    print w.get_emulsification_wind(None, start_time)
    # input wave height should hav overwhelmed
    assert w.get_emulsification_wind(None, start_time) > 3.0


def test_get_emulsification_wind_with_wave_height2():
    wind = constant_wind(10., 0)
    water = Water()
    water.wave_height = 2.0
    w = Waves(wind, water)

    print w.get_value(None, start_time)

    print w.get_emulsification_wind(None, start_time)
    # input wave height should not have overwhelmed wind speed
    assert w.get_emulsification_wind(None, start_time) == 10.0
