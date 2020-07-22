#!/usr/bin/env python
"""
Unit tests for CyOSSMTime class
"""
import os

from pytest import raises
import pytest

import numpy as np

# import basic_types and subsequently lib_gnome
from gnome import basic_types
from gnome.basic_types import ts_format, seconds, velocity_rec

from gnome.cy_gnome.cy_ossm_time import CyOSSMTime, CyTimeseries

from ..conftest import testdata


@pytest.mark.parametrize('obj', [CyOSSMTime, CyTimeseries])
def test_init_exceptions(obj):
    with raises(IOError):
        # bad path
        obj(filename='WindDataFromGnome.WNDX',
            file_format=ts_format.magnitude_direction)

    with raises(ValueError):
        # insufficient input info
        obj(filename=testdata['timeseries']['wind_ts'])

    with raises(ValueError):
        # insufficient input info
        obj(filename=testdata['timeseries']['wind_bad_units'],
            file_format=ts_format.magnitude_direction)

    with raises(ValueError):
        # file_format has wrong int type
        obj(filename=testdata['timeseries']['wind_ts'],
            file_format=0)


@pytest.mark.parametrize('obj', [CyOSSMTime, CyTimeseries])
def test_initial_properties(obj):
    '''
        todo: OSSM needs to read station + location info if found in file
    '''
    # 5 is ts_format.magnitude_direction
    cy = obj(testdata['timeseries']['wind_ts'], 5)

    assert cy.station is None
    assert cy.station_location is None
    assert cy.extrapolation_is_allowed is False

    assert cy.user_units == 'knots'
    assert (cy.filename == os.path.split(testdata['timeseries']['wind_ts'])[1])
    assert cy.scale_factor == 1.0


@pytest.mark.parametrize('obj', [CyOSSMTime, CyTimeseries])
def test_init_arguments(obj):
    '''
        TODO: I think the file_format is not exposed in the Cython object.
              This is why we don't test the default value for file_format.
              We need to make this better.
    '''
    # test the scale_factor argument and all permutations.
    cy = obj(testdata['timeseries']['wind_ts'], 5,
             scale_factor=2)

    assert cy.scale_factor == 2.0

    cy = obj(testdata['timeseries']['wind_ts'], 5,
             scale_factor=2.0)

    assert cy.scale_factor == 2.0

    # test the extrapolation_is_allowed flag and all permutations.
    cy = obj(testdata['timeseries']['wind_ts'], 5,
             extrapolation_is_allowed=True)

    assert cy.extrapolation_is_allowed is True

    cy = obj(testdata['timeseries']['wind_ts'], 5,
             extrapolation_is_allowed=False)

    assert cy.extrapolation_is_allowed is False

    # try it with an int.
    cy = obj(testdata['timeseries']['wind_ts'], 5,
             extrapolation_is_allowed=1)

    assert cy.extrapolation_is_allowed is True

    cy = obj(testdata['timeseries']['wind_ts'], 5,
             extrapolation_is_allowed=0)

    assert cy.extrapolation_is_allowed is False

    # try it with a float.
    cy = obj(testdata['timeseries']['wind_ts'], 5,
             extrapolation_is_allowed=1.0)

    assert cy.extrapolation_is_allowed is True

    cy = obj(testdata['timeseries']['wind_ts'], 5,
             extrapolation_is_allowed=0.0)

    assert cy.extrapolation_is_allowed is False


@pytest.mark.parametrize('obj', [CyOSSMTime, CyTimeseries])
def test_init_units(obj):
    """
    Test __init__
    - correct path
    Updated so the user units are read from filename
    """
    ossmT2 = obj(filename=testdata['timeseries']['wind_ts'],
                 file_format=ts_format.magnitude_direction)
    assert ossmT2.user_units == 'knots'


class TestObjectSerialization:
    '''
        Test all the serialization and deserialization methods that are
        available to the CyOSSMTime object.
    '''
    @pytest.mark.parametrize('obj', [CyOSSMTime, CyTimeseries])
    def test_repr(self, obj):
        '''
            Test that the repr method produces a string capable of reproducing
            the object.
        '''
        import gnome
        from numpy import array

        ossmT = obj(filename=testdata['timeseries']['wind_ts'],
                    file_format=ts_format.magnitude_direction)

        new_ossm = eval(repr(ossmT))

        assert new_ossm == ossmT
        assert repr(new_ossm) == repr(ossmT)


'Tests for child CyTimeseries object'


class TestCyTimeseries:
    """
    Test __init__ method and the exceptions it throws for CyOSSMTime
    """
    tval = np.array([(0, (1, 2)), (1, (2, 3))],
                    dtype=basic_types.time_value_pair)

    def test_init_from_timeseries(self):
        """
        Sets the time series in OSSMTimeValue_c equal to the
        externally supplied numpy array containing time_value_pair data
        It then reads it back to make sure data was set correctly
        """
        ossm = CyTimeseries(timeseries=self.tval)
        t_val = ossm.timeseries
        msg = ('{0}().get_time_value() did not return expected '
               'numpy array').format(ossm.__class__.__name__)
        np.testing.assert_array_equal(t_val, self.tval, msg, 0)
        assert ossm.user_units == 'undefined'  # meters/second
        assert ossm.station_location is None
        assert ossm.station is None
        assert ossm.filename is None
        assert ossm.scale_factor == 1.0

    def test_get_time_value(self):
        ossm = CyTimeseries(timeseries=self.tval)

        actual = np.array(self.tval['value'], dtype=velocity_rec)
        time = np.array(self.tval['time'], dtype=seconds)
        vel_rec, _err = ossm.get_time_value(time)
        print vel_rec

        tol = 1e-6
        msg = ('{0} is not within a tolerance of '
               '{1}'.format('get_time_value', tol))

        np.testing.assert_allclose(vel_rec['u'], actual['u'], tol, tol, msg, 0)
        np.testing.assert_allclose(vel_rec['v'], actual['v'], tol, tol, msg, 0)

    def test_get_time_out_of_bounds(self):
        time_values = np.array([(1, (1, 2)), (2, (2, 3))],
                               dtype=basic_types.time_value_pair)

        ossm = CyTimeseries(timeseries=time_values)

        # testing before the start time
        with pytest.raises(IndexError):
            _vel_rec, _err = ossm.get_time_value(np.array([0], dtype=seconds))

        # testing after the end time
        with pytest.raises(IndexError):
            _vel_rec, _err = ossm.get_time_value(np.array([3], dtype=seconds))

        # now we allow extrapolation
        ossm.extrapolation_is_allowed = True

        begin_value, _err = ossm.get_time_value(np.array([1], dtype=seconds))
        end_value, _err = ossm.get_time_value(np.array([2], dtype=seconds))

        # before the start time should now return without an exception
        # and it should return the value associated with the start time.
        vel_rec, _err = ossm.get_time_value(np.array([0], dtype=seconds))
        assert vel_rec == begin_value

        # after the end time should now return without an exception
        # and it should return the value associated with the end time.
        vel_rec, _err = ossm.get_time_value(np.array([3], dtype=seconds))
        assert vel_rec == end_value

    def test__set_time_value_handle_none(self):
        """Check TypeError exception for private method"""
        try:
            ossm = CyTimeseries(timeseries=self.tval)
            ossm._set_time_value_handle(None)
        except TypeError:
            assert True

    def test_timeseries(self):
        """
        test setting the timeseries using timeseries property
        """
        ossmT = CyTimeseries(timeseries=self.tval)
        t_val = ossmT.timeseries

        print 't_val before:', t_val['value']
        # need to learn how to do the following in 1 line of code
        t_val['value']['u'] += 2
        t_val['value']['v'] += 2
        print 't_val after:', t_val['value']

        ossmT.timeseries = t_val
        new_val = ossmT.timeseries

        tol = 1e-10
        msg = ('{0} is not within a tolerance of '
               '{1}'.format('get_time_value', tol))
        np.testing.assert_allclose(t_val['time'], new_val['time'],
                                   tol, tol, msg, 0)
        np.testing.assert_allclose(t_val['value']['u'], new_val['value']['u'],
                                   tol, tol, msg, 0)
        np.testing.assert_allclose(t_val['value']['v'], new_val['value']['v'],
                                   tol, tol, msg, 0)

    def test_readfile_constant_wind(self):
        """
        Read contents for a filename that contains a constant wind.
        This will be just 1 line in the text filename.
        Test get_time_values method. It gets the time value pair
        for the constant wind per the data filename.
        This test just gets the time value pair that was created
        from the filename. It then invokes get_time_value for that time
        in the time series and also looks at the velocity 100 sec later.
        Since wind is constant, the value should be unchanged
        """
        ossmT = CyTimeseries(filename=testdata['timeseries']['wind_constant'],
                             file_format=ts_format.magnitude_direction)
        # Let's see what is stored in the Handle to expected result
        t_val = ossmT.timeseries

        actual = np.array(t_val['value'], dtype=velocity_rec)
        time = np.array(t_val['time'] + (0, 100), dtype=seconds)

        vel_rec, _err = ossmT.get_time_value(time)

        tol = 1e-6
        msg = ('{0} is not within a tolerance of '
               '{1}'.format('get_time_value', tol))

        for vel in vel_rec:
            np.testing.assert_allclose(vel['u'], actual['u'], tol, tol,
                                       msg, 0)
            np.testing.assert_allclose(vel['v'], actual['v'], tol, tol,
                                       msg, 0)


def test_get_num_values():
    ts = CyOSSMTime(testdata['timeseries']['wind_ts'], 5)
    # 5 is ts_format.magnitude_direction
    assert ts.get_num_values() == 4


if __name__ == '__main__':
    # tt = TestTimeSeriesInit()
    # tt.test_init_timeseries()
    # tt.test_get_time_value()
    T = TestObjectSerialization()
    T.test_repr()
