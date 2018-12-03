'''
Test various element types available for the Spills
Element Types are very simple classes. They simply define the initializers.
These are also tested in the test_spill_container module since it allows for
more comprehensive testing

FIXME: a number of these tests require a spill object -- those tests really
       should be moved to the spill object -- or maybe not used at all?
'''

from datetime import datetime, timedelta
import os

import pytest
from pytest import raises

import numpy as np

from oil_library import _sample_oils

import gnome
from gnome.utilities.distributions import (NormalDistribution,
                                           UniformDistribution,
                                           LogNormalDistribution,
                                           WeibullDistribution)
from gnome.environment import Water
from gnome.spill.elements import (InitWindages,
                                  InitRiseVelFromDist,
                                  InitRiseVelFromDropletSizeFromDist,
                                  floating,
                                  ElementType)

from gnome.spill import Spill, Release
from oil_library import get_oil_props
from gnome.persist import load

from ..conftest import mock_sc_array_types, mock_append_data_arrays, test_oil

""" Helper functions """
# first key in windages array must be 'windages' because test function:
# test_element_type_serialize_deserialize assumes this is the case
windages = mock_sc_array_types(['windages',
                                'windage_range',
                                'windage_persist'])
mass_array = mock_sc_array_types(['mass'])
rise_vel_array = mock_sc_array_types(['rise_vel'])
rise_vel_diameter_array = mock_sc_array_types(['rise_vel',
                                               'droplet_diameter'])

num_elems = 10
oil = test_oil


def assert_dataarray_shape_size(arr_types, data_arrays, num_released):
    for key, val in arr_types.iteritems():
        assert data_arrays[key].dtype == val.dtype
        assert data_arrays[key].shape == (num_released,) + val.shape


""" Initializers - following are used for parameterizing tests """
fcn_list = (InitWindages(),
            InitRiseVelFromDist(distribution=UniformDistribution()),
            InitRiseVelFromDist(distribution=NormalDistribution(mean=0,
                                                                sigma=0.1)),
            InitRiseVelFromDist(distribution=LogNormalDistribution(mean=0,
                                                                   sigma=0.1)),
            InitRiseVelFromDist(distribution=WeibullDistribution(alpha=1.8,
                                                                 lambda_=(1 / (.693 ** (1 / 1.8)))
                                                                 )),
            InitRiseVelFromDropletSizeFromDist(NormalDistribution(mean=0,
                                                                  sigma=0.1))
            )

arrays_ = (windages,
           rise_vel_array, rise_vel_array, rise_vel_array, rise_vel_array,
           rise_vel_diameter_array)

spill_list = (None, None, None, None, None,
              Spill(Release(datetime.now()), water=Water()))


@pytest.mark.parametrize(("fcn", "arr_types", "spill"),
                         zip(fcn_list, arrays_, spill_list))
def test_correct_particles_set_by_initializers(fcn, arr_types, spill):
    '''
    Tests that the correct elements (ones that
    were released last) are initialized
    '''
    # let's only set the values for the last 10 elements
    # this is not how it would be used, but this is just to make sure
    # the values for the correct elements are set
    data_arrays = mock_append_data_arrays(arr_types, num_elems)
    data_arrays = mock_append_data_arrays(arr_types, num_elems, data_arrays)
    substance = get_oil_props(oil)

    if spill is not None:
        spill.release.num_elements = 10

    fcn.initialize(num_elems, spill, data_arrays, substance)

    assert_dataarray_shape_size(arr_types, data_arrays, num_elems * 2)

    # contrived example since particles will be initialized for every timestep
    # when they are released. But just to make sure that only values for the
    # latest released elements are set
    for key in data_arrays:
        assert np.all(0 == data_arrays[key][:num_elems])

        # values for these particles should be initialized to non-zero
        assert np.any(0 != data_arrays[key][-num_elems:])


@pytest.mark.parametrize("fcn", fcn_list)
def test_element_type_serialize_deserialize(fcn):
    '''
    test serialization/deserialization of ElementType for various initiailzers
    '''
    element_type = ElementType(initializers=[fcn], substance=oil)

    json_ = element_type.serialize()
    element_type2 = ElementType.deserialize(json_)

    assert element_type == element_type2


class TestInitConstantWindageRange:
    @pytest.mark.parametrize(("fcn", "array"),
                             [(InitWindages(), windages),
                              (InitWindages([0.02, 0.03]), windages),
                              (InitWindages(), windages),
                              (InitWindages(windage_persist=-1), windages)])
    def test_initailize_InitConstantWindageRange(self, fcn, array):
        'tests initialize method'
        data_arrays = mock_append_data_arrays(array, num_elems)
        fcn.initialize(num_elems, None, data_arrays)
        assert_dataarray_shape_size(array, data_arrays, num_elems)

        assert np.all(data_arrays['windage_range'] == fcn.windage_range)
        assert np.all(data_arrays['windage_persist'] == fcn.windage_persist)

        np.all(data_arrays['windages'] != 0)
        np.all(data_arrays['windages'] >= data_arrays['windage_range'][:, 0])
        np.all(data_arrays['windages'] <= data_arrays['windage_range'][:, 1])

    def test_exceptions(self):
        bad_wr = [-1, 0]
        bad_wp = 0
        obj = InitWindages()
        with raises(ValueError):
            InitWindages(windage_range=bad_wr)

        with raises(ValueError):
            InitWindages(windage_persist=bad_wp)

        with raises(ValueError):
            obj.windage_range = bad_wr

        with raises(ValueError):
            obj.windage_persist = bad_wp


def test_initialize_InitRiseVelFromDist_uniform():
    'Test initialize data_arrays with uniform dist'
    data_arrays = mock_append_data_arrays(rise_vel_array, num_elems)

    fcn = InitRiseVelFromDist(distribution=UniformDistribution())
    fcn.initialize(num_elems, None, data_arrays)

    assert_dataarray_shape_size(rise_vel_array, data_arrays, num_elems)

    assert np.all(0 != data_arrays['rise_vel'])
    assert np.all(data_arrays['rise_vel'] <= 1)
    assert np.all(data_arrays['rise_vel'] >= 0)


def test_initialize_InitRiseVelFromDropletDist_weibull():
    'Test initialize data_arrays with Weibull dist'
    num_elems = 10
    data_arrays = mock_append_data_arrays(rise_vel_diameter_array, num_elems)
    substance = get_oil_props(oil)
    spill = Spill(Release(datetime.now()), water=Water())

    # (.001*.2) / (.693 ** (1 / 1.8)) - smaller droplet test case, in mm
    #                                   so multiply by .001
    dist = WeibullDistribution(alpha=1.8, lambda_=.000248)
    fcn = InitRiseVelFromDropletSizeFromDist(dist)
    fcn.initialize(num_elems, spill, data_arrays, substance)

    assert_dataarray_shape_size(rise_vel_array, data_arrays, num_elems)

    assert np.all(0 != data_arrays['rise_vel'])
    assert np.all(0 != data_arrays['droplet_diameter'])


def test_initialize_InitRiseVelFromDropletDist_weibull_with_min_max():
    'Test initialize data_arrays with Weibull dist'
    num_elems = 1000
    data_arrays = mock_append_data_arrays(rise_vel_diameter_array, num_elems)
    substance = get_oil_props(oil)
    spill = Spill(Release(datetime.now()), water=Water())

    # (.001*3.8) / (.693 ** (1 / 1.8)) - larger droplet test case, in mm
    #                                    so multiply by .001
    dist = WeibullDistribution(min_=0.002, max_=0.004,
                               alpha=1.8, lambda_=.00456)
    fcn = InitRiseVelFromDropletSizeFromDist(dist)
    fcn.initialize(num_elems, spill, data_arrays, substance)

    # test for the larger droplet case above
    assert np.all(data_arrays['droplet_diameter'] >= .002)

    # test for the larger droplet case above
    assert np.all(data_arrays['droplet_diameter'] <= .004)


def test_initialize_InitRiseVelFromDist_normal():
    """
    test initialize data_arrays with normal dist
    assume normal distribution works fine - so statistics (mean, var) are not
    tested
    """
    num_elems = 1000
    data_arrays = mock_append_data_arrays(rise_vel_array, num_elems)

    dist = NormalDistribution(mean=0, sigma=0.1)
    fcn = InitRiseVelFromDist(distribution=dist)
    fcn.initialize(num_elems, None, data_arrays)

    assert_dataarray_shape_size(rise_vel_array, data_arrays, num_elems)

    assert np.all(0 != data_arrays['rise_vel'])


""" Element Types"""
# additional array_types corresponding with ElementTypes for following test
arr_types = windages
rise_vel = mock_sc_array_types(['rise_vel'])
rise_vel.update(arr_types)

oil = test_oil

inp_params = [((floating(substance=oil),
                ElementType([InitWindages()], substance=oil)), arr_types),
              ((floating(substance=oil),
                ElementType([InitWindages(),
                             InitRiseVelFromDist(distribution=UniformDistribution())],
                            substance=oil)), rise_vel),
              ((floating(substance=oil),
                ElementType([InitRiseVelFromDist(distribution=UniformDistribution())],
                            substance=oil)), rise_vel),
              ]


@pytest.mark.parametrize(("elem_type", "arr_types"), inp_params)
def test_element_types(elem_type, arr_types, sample_sc_no_uncertainty):
    """
    Tests data_arrays associated with the spill_container's
    initializers get initialized to non-zero values.
    Uses sample_sc_no_uncertainty fixture defined in conftest.py
    It initializes a SpillContainer object with two Spill objects. For first
    Spill object, set element_type=floating() and for the second Spill object,
    set element_type=elem_type[1] as defined in the tuple in inp_params
    """
    sc = sample_sc_no_uncertainty
    release_t = None

    for idx, spill in enumerate(sc.spills):
        spill.release.num_elements = 20
        spill.element_type = elem_type[idx]

        if release_t is None:
            release_t = spill.release.release_time

        # set release time based on earliest release spill
        if spill.release.release_time < release_t:
            release_t = spill.release.release_time

    time_step = 3600
    num_steps = 4
    sc.prepare_for_model_run(arr_types)

    for step in range(num_steps):
        current_time = release_t + timedelta(seconds=time_step * step)
        sc.release_elements(time_step, current_time)

        for spill in sc.spills:
            spill_mask = sc.get_spill_mask(spill)
            # todo: need better API for access
            s_arr_types = spill.array_types

            if np.any(spill_mask):
                for key in arr_types:
                    if key in s_arr_types:
                        assert np.all(sc[key][spill_mask] != 0)
                    else:
                        if sc.array_types[key].initial_value is not None:
                            assert np.all(sc[key][spill_mask] ==
                                          sc.array_types[key].initial_value)

@pytest.mark.parametrize(("fcn"), fcn_list)
def test_serialize_deserialize_initializers(fcn):
    n_obj = fcn.__class__.deserialize(fcn.serialize())

    assert n_obj == fcn


test_l = []
test_l.extend(fcn_list)
test_l.extend([ElementType(initializers=fcn, substance=test_oil)
               for fcn in fcn_list])
test_l.append(floating(substance=test_oil))


def test_serialize_deserialize():
    '''
    serialize/deserialize for 'save' option is tested in test_save_load
    This tests serialize/deserilize with 'webapi' option
    '''
    et = floating()
    n_et = ElementType.deserialize(et.serialize())

    # for webapi, make new objects from nested objects before creating
    # new element_type
    # following is not a requirement for webapi, but it is infact the case
    assert n_et == et


def test_standard_density():
    et = floating()
    dict_ = et.serialize()
    assert dict_['standard_density'] == 1000.0

    et = floating(substance=oil)
    dict_ = et.serialize()
    assert dict_['standard_density'] == et.substance.density_at_temp(288.15)


@pytest.mark.parametrize(("test_obj"), test_l)
def test_save_load(saveloc_, test_obj):
    '''
    test save/load for initializers and for ElementType objects containing
    each initializer. Tests serialize/deserialize as well.
    These are stored as nested objects in the Spill but this should also work
    so test it here
    '''
    json_, savefile, refs = test_obj.save(saveloc_)
    test_obj2 = test_obj.__class__.load(savefile)
    assert test_obj == test_obj2


@pytest.mark.parametrize("substance", [test_oil,
                                       get_oil_props(test_oil)])
def test_element_type_init(substance):
    et = ElementType(substance=substance)
    if isinstance(substance, basestring):
        try:
            assert et.substance.get('name') == substance
        except AssertionError:
            assert et.substance.get('name') == _sample_oils[substance].name
    elif isinstance(substance, int):
        assert et.substance.get('id') == substance
    else:
        assert et.substance.get('name') == substance.get('name')


def test_exception():
    with pytest.raises(Exception):
        ElementType(substance='junk')
