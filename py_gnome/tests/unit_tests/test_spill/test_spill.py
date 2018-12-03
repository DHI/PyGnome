#!/usr/bin/env python

"""
Tests Spill() class and the various release() classes

Release objects were factored out but the tests are still all in here
Simple tests that do not use the Spill object have been moved to
test_release.py - this module was getting too big

todo: could still be refactored and made more concise
"""

from datetime import datetime, timedelta
import copy

import pytest
from pytest import raises

import numpy as np

import unit_conversion as uc

from gnome.model import Model
from gnome.environment import Water
from gnome.movers import RandomMover
from gnome.spill import (Spill,
                         Release,
                         point_line_release_spill,
                         SpatialRelease,
                         InitElemsFromFile,
                         grid_spill,
                         )
from gnome.spill.elements import (floating,
                                  ElementType)

from gnome.spill_container import SpillContainer

from ..conftest import mock_sc_array_types, mock_append_data_arrays, test_oil, testdata


# Used to mock SpillContainer functionality of creating/appending data_arrays
# Only care about 'positions' array type for all spills, no need to define
# and carry remaining numpy arrays
arr_types = mock_sc_array_types({'positions', 'mass'})


@pytest.mark.parametrize(("element_type", "amount"), [(None, None),
                                                      (None, 10.0),
                                                      (ElementType(), None),
                                                      (ElementType(), 1.0),
                                                      ])
def test_init(element_type, amount):
    '''
    Test various initializations
    '''
    spill = Spill(Release(release_time=datetime.now()),
                  element_type=element_type,
                  amount=amount,
                  units='kg'
                  )

    if element_type is None:
        assert np.all(spill.windage_range == (0.01, 0.04))
        assert spill.windage_persist == 900
        # no need to test this in spill -- it shouldn't know about initializers
    #     assert len(spill.initializers) == 1  # add windages
    # else:
    #     assert len(spill.initializers) == 0

    assert spill.release_duration == 0


@pytest.mark.parametrize(("amount", "units"), [(10.0, 'm^3'),
                                               (10.0, 'kg')])
def test_amount_mass_vol(amount, units):
    '''
    ensure mass is being returned correctly when 'amount' is initialized wtih
    'mass' or 'volume'
    '''
    water = Water()
    spill = Spill(Release(datetime.now()),
                  amount=amount,
                  units=units,
                  substance=test_oil,
                  water=water)
    assert spill.amount == amount
    assert spill.units == units

    if units in Spill.valid_vol_units:
        # use 15C (288.15K) for mass<=>volume conversion
        exp_mass = (spill.substance.density_at_temp(288.15) *
                    uc.convert('Volume', units, 'm^3', spill.amount))
    else:
        exp_mass = uc.convert('Mass', units, 'kg', spill.amount)
    assert spill.get_mass() == exp_mass

    exp_mass_g = exp_mass * 1000
    assert spill.get_mass('g') == exp_mass_g


def test_init_exceptions():

    with raises(TypeError):
        Spill(Release(datetime.now()), amount=10)

    with raises(ValueError):
        Spill(Release(release_time=datetime.now()),
              element_type=floating(windage_range=(-1, 0)))

    with raises(ValueError):
        Spill(Release(release_time=datetime.now()),
              element_type=floating(windage_persist=0))


def test_deepcopy():
    """
    tests that a deepcopy results in a copy so objects are not the same
    todo: how should this work?
    """
    sp1 = Spill(Release(release_time=datetime.now().replace(microsecond=0)))
    sp2 = copy.deepcopy(sp1)
    assert sp1 is not sp2
    assert sp1.id != sp2.id

    # try deleting the copy, and see if any errors result
    del sp2
    del sp1


def test_copy():
    """
    TODO: how should this work
    """
    sp1 = Spill(Release(release_time=datetime.now().replace(microsecond=0)))
    sp2 = copy.copy(sp1)
    assert sp1 is not sp2
    assert sp1.id != sp2.id

    # try deleting the copy, and see if any errors result
    del sp1
    del sp2


def test_uncertain_copy():
    """
    only tests a few things...
    """
    spill = point_line_release_spill(num_elements=100,
                                     start_position=(28, -78, 0.),
                                     release_time=datetime.now(),
                                     end_position=(29, -79, 0.),
                                     end_release_time=(datetime.now() +
                                                       timedelta(hours=24)),
                                     element_type=floating(windage_range=(.02,
                                                                          .03),
                                                           windage_persist=-1)
                                     )

    u_spill = spill.uncertain_copy()

    assert u_spill is not spill
    assert np.array_equal(u_spill.release.start_position,
                          spill.release.start_position)
    del spill
    del u_spill


class Test_point_line_release_spill:

    num_elements = 10
    start_position = (-128.3, 28.5, 0)
    release_time = datetime(2012, 8, 20, 13)
    timestep = 3600  # one hour in seconds

    # nominal test cases for parametrizing some tests in this class
    nom_positions = [((-128.0, 28.0, 0.),
                      (-129.0, 29.0, 0.)),  # nominal test
                     ((-128.0, 28.0, 0.),
                      (-129.0, 29.0, 1.))]  # w/ z!=0

    def _release(self, sp, release_time, timestep, data_arrays):
        num = sp.num_elements_to_release(release_time, timestep)
        if num > 0:
            # only invoked if particles are released
            data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
            sp.set_newparticle_values(num, release_time, timestep, data_arrays)
        else:
            # initialize all data arrays even if no particles are released
            if data_arrays == {}:
                data_arrays = mock_append_data_arrays(arr_types, num,
                                                      data_arrays)
        return (num, data_arrays)

    def release_and_assert(self, sp, release_time, timestep,
                           data_arrays, expected_num_released):
        """
        Helper function. All tests except one invoke this function.
        For each release test in this function, group the common actions
        in this function.

        :param sp: spill object
        :param release_time: release time for particles
        :param timestep: timestep to use for releasing particles
        :param data_arrays: data_arrays to which new elements are appended.
            dict containing numpy arrays for values. Serves the same
            function as gnome.spill_container.SpillContainer().data_arrays
        :param expected_num_released: number of particles that we expect
            to release for this timestep. This is used for assertions.

        It returns a copy of the data_arrays after appending the newly
        released particles to it. This is so the caller can do more
        assertions against it.
        Also so we can keep appending to data_arrays since that is what the
        SpillContainer will work until a rewind.
        """
        prev_num_rel = sp.num_released
        (num, data_arrays) = \
            self._release(sp, release_time, timestep, data_arrays)
        assert num == expected_num_released

        assert sp.num_released == prev_num_rel + expected_num_released
        assert data_arrays['positions'].shape == (sp.num_released, 3)

        return data_arrays

    def test_init(self):
        """
        Tests object initializes correctly.
        - self.end_position == self.start_position if it is not given as input
        - self.end_release_time == self.release_time if not given as input
        """
        sp = point_line_release_spill(num_elements=self.num_elements,
                                      start_position=self.start_position,
                                      release_time=self.release_time)

        release = sp.release
        print "in test_init: release", release
        assert release.num_elements == self.num_elements
        assert (np.all(release.start_position == self.start_position) and
                np.all(release.end_position is None))
        assert (np.all(release.release_time == self.release_time) and
                release.end_release_time is None)
        assert sp.release_duration == 0

    def test_noparticles_model_run_after_release_time(self):
        """
        Tests that the spill doesn't release anything if the first call
        to release elements is after the release time.
        This so that if the user sets the model start time after the spill,
        they don't get anything.
        """
        sp = point_line_release_spill(num_elements=self.num_elements,
                                      start_position=self.start_position,
                                      release_time=self.release_time)

        # Test no particles released for following conditions
        #     current_time > spill's release_time
        #     current_time + timedelta > spill's release_time
        for rel_delay in range(1, 3):
            num = sp.num_elements_to_release(self.release_time
                                             + timedelta(hours=rel_delay),
                                             time_step=30 * 60)
            assert num == 0

        # rewind and it should work
        sp.rewind()
        data_arrays = self.release_and_assert(sp, self.release_time, 30 * 60,
                                              {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)

    def test_noparticles_model_run_before_release_time(self):
        """
        Tests that the spill doesn't release anything if the first call
        to num_elements_to_release is before the release_time + timestep.
        """
        sp = point_line_release_spill(num_elements=self.num_elements,
                                      start_position=self.start_position,
                                      release_time=self.release_time)
        print 'release_time:', self.release_time
        timestep = 360  # seconds

        # right before the release
        num = sp.num_elements_to_release(self.release_time -
                                         timedelta(seconds=360), timestep)
        assert num == 0

        # right after the release
        data_arrays = self.release_and_assert(sp,
                                              self.release_time -
                                              timedelta(seconds=1),
                                              timestep, {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)

    def test_inst_point_release(self):
        """
        Test all particles for an instantaneous point release are released
        correctly.
        - also tests that once all particles have been released, no new
          particles are released in subsequent steps
        """
        sp = point_line_release_spill(num_elements=self.num_elements,
                                      start_position=self.start_position,
                                      release_time=self.release_time,
                                      amount=100,
                                      units='kg')
        assert sp.release_duration == 0
        timestep = 3600  # seconds

        # release all particles
        data_arrays = self.release_and_assert(sp, self.release_time,
                                              timestep, {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)

        # no more particles to release since all particles have been released
        num = sp.num_elements_to_release(self.release_time + timedelta(10),
                                         timestep)
        assert num == 0

        # reset and try again
        sp.rewind()
        assert sp.num_released == 0
        num = sp.num_elements_to_release(self.release_time - timedelta(10),
                                         timestep)
        assert num == 0
        assert sp.num_released == 0

        # release all particles
        data_arrays = self.release_and_assert(sp, self.release_time,
                                              timestep, {}, self.num_elements)
        assert np.alltrue(data_arrays['positions'] == self.start_position)
        assert data_arrays['mass'].sum() == sp.get_mass('kg')

    def test_cont_point_release(self):
        """
        Time varying release so release_time < end_release_time. It releases
        particles over 10 hours. start_position == end_position so it is still
        a point source

        It simulates how particles could be released by a Model with a variable
        timestep
        """
        sp = point_line_release_spill(num_elements=100,
                                      start_position=self.start_position,
                                      release_time=self.release_time,
                                      end_release_time=(self.release_time +
                                                        timedelta(hours=10)),
                                      amount=123,
                                      units='kg')

        assert (sp.release_duration ==
                timedelta(hours=10).total_seconds())
        timestep = 3600  # one hour in seconds

        """
        Release elements incrementally to test continuous release

        4 times and timesteps over which elements are released. The timesteps
        are variable
        """
        # at exactly the release time -- ten get released at start_position
        # one hour into release -- ten more released
        # keep appending to data_arrays in same manner as SpillContainer would
        # 1-1/2 hours into release - 5 more
        # at end -- rest (75 particles) should be released
        data_arrays = {}
        delay_after_rel_time = [timedelta(hours=0),
                                timedelta(hours=1),
                                timedelta(hours=2),
                                timedelta(hours=10)]
        # todo: figure out how we want point/line release to work!
        # ts = [timestep, timestep, timestep / 2, timestep]
        # exp_num_released = [10, 10, 5, 75]
        ts = [timestep, timestep, timestep * 8, timestep]
        exp_num_released = [10, 10, 80, 0]

        for ix in range(4):
            data_arrays = self.release_and_assert(sp,
                                                  self.release_time +
                                                  delay_after_rel_time[ix],
                                                  ts[ix], data_arrays,
                                                  exp_num_released[ix])
            assert np.alltrue(data_arrays['positions'] == self.start_position)

        assert sp.num_released == sp.release.num_elements
        assert np.allclose(data_arrays['mass'].sum(), sp.get_mass('kg'),
                           atol=1e-6)

        # rewind and reset data arrays for new release
        sp.rewind()
        data_arrays = {}

        # 360 second time step: should release first LE
        # In 3600 sec, 10 particles are released so one particle every 360sec
        # release one particle each over (360, 720) seconds
        for ix in range(2):
            ts = ix * 360 + 360
            data_arrays = self.release_and_assert(sp, self.release_time, ts,
                                                  data_arrays, 1)
            assert np.alltrue(data_arrays['positions'] == self.start_position)

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_inst_line_release(self, start_position, end_position):
        """
        release all elements instantaneously but
        start_position != end_position so they are released along a line
        """
        sp = point_line_release_spill(num_elements=11,
                                      start_position=start_position,
                                      release_time=self.release_time,
                                      end_position=end_position)
        data_arrays = self.release_and_assert(sp, self.release_time,
                                              600, {}, sp.release.num_elements)

        assert data_arrays['positions'].shape == (11, 3)
        assert np.array_equal(data_arrays['positions'][:, 0],
                              np.linspace(-128, -129, 11))
        assert np.array_equal(data_arrays['positions'][:, 1],
                              np.linspace(28, 29, 11))

        assert sp.num_released == 11

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_cont_line_release_first_timestep(self,
                                              start_position, end_position):
        """
        testing a release that is releasing while moving over time; however,
        all particles are released in 1st timestep

        In this one it all gets released in the first time step.
        """
        sp = point_line_release_spill(num_elements=11,
                                      start_position=start_position,
                                      release_time=self.release_time,
                                      end_position=end_position,
                                      end_release_time=(self.release_time +
                                                        timedelta(minutes=100))
                                      )
        assert (sp.release_duration == timedelta(minutes=100).total_seconds())

        timestep = 100 * 60

        # the full release over one time step
        # (plus a tiny bit to get the last one)
        data_arrays = self.release_and_assert(sp, self.release_time,
                                              timestep + 1, {},
                                              sp.release.num_elements)

        assert data_arrays['positions'].shape == (11, 3)
        assert np.array_equal(data_arrays['positions'][:, 0],
                              np.linspace(-128, -129, 11))
        assert np.array_equal(data_arrays['positions'][:, 1],
                              np.linspace(28, 29, 11))

        assert sp.num_released == 11

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_cont_line_release_multiple_timesteps(self,
                                                  start_position,
                                                  end_position):
        """
        testing a release that is releasing while moving over time

        Release 1/10 of particles (10 out of 100) over two steps. Then release
        the remaining particles in the last step
        """
        num_elems = 100
        sp = point_line_release_spill(num_elems,
                                      start_position=start_position,
                                      release_time=self.release_time,
                                      end_position=end_position,
                                      end_release_time=(self.release_time +
                                                        timedelta(minutes=100))
                                      )
        rel = sp.release
        lats = np.linspace(rel.start_position[0], rel.end_position[0],
                           num_elems)
        lons = np.linspace(rel.start_position[1], rel.end_position[1],
                           num_elems)
        z = np.linspace(rel.start_position[2], rel.end_position[2],
                        num_elems)

        # at release time with time step of 1/10 of release_time
        # 1/10th of total particles are expected to be released
        # release 10 particles over two steps. Then release remaining particles
        # over the last timestep
        timestep = 600
        data_arrays = {}
        ts = [timestep, timestep,
              (rel.end_release_time - rel.release_time).total_seconds() -
              2*timestep]
        exp_elems = [10, 10, 80]
        time = self.release_time
        for ix in range(len(ts)):
            data_arrays = self.release_and_assert(sp,
                                                  time,
                                                  ts[ix], data_arrays,
                                                  exp_elems[ix])
            assert np.allclose(data_arrays['positions'][:, 0],
                               lats[:sp.num_released], atol=1e-10)
            assert np.allclose(data_arrays['positions'][:, 1],
                               lons[:sp.num_released], atol=1e-10)

            if np.any(z != 0):
                assert np.allclose(data_arrays['positions'][:, 2],
                                   z[:sp.num_released], atol=1e-10)

            time += timedelta(seconds=ts[ix])

    @pytest.mark.parametrize(('start_position', 'end_position'), nom_positions)
    def test_cont_line_release_vary_timestep(self,
                                             start_position,
                                             end_position,
                                             vary_timestep=True):
        """
        testing a release that is releasing while moving over time

        making sure it's right for the full release
        - vary the timestep if 'vary_timestep' is True
        - the release rate is a constant

        Same test with vary_timestep=False is used by
        test_cardinal_direction_release(..)
        """
        sp = point_line_release_spill(num_elements=50,
                                      start_position=start_position,
                                      release_time=self.release_time,
                                      end_position=end_position,
                                      end_release_time=(self.release_time +
                                                        timedelta(minutes=50)),
                                      amount=1000,
                                      units='kg')

        # start before release
        time = self.release_time - timedelta(minutes=10)
        delta_t = timedelta(minutes=10)
        num_rel_per_min = 1  # release 50 particles in 50 minutes
        data_arrays = {}

        mult = 0
        if not vary_timestep:
            mult = 1
        # end after release - release 10 particles at every step
        while time < sp.release.end_release_time:
            var_delta_t = delta_t   # vary delta_t
            exp_num_rel = 0
            if (time + delta_t > self.release_time):
                # change the rate at which particles are released
                if vary_timestep:
                    mult += 1

                var_delta_t = mult * delta_t
                timestep_min = var_delta_t.seconds / 60
                exp_num_rel = min(sp.num_elements -
                                  sp.num_released,
                                  num_rel_per_min * timestep_min)

            data_arrays = self.release_and_assert(sp,
                                                  time,
                                                  var_delta_t.total_seconds(),
                                                  data_arrays,
                                                  exp_num_rel)
            time += var_delta_t

        assert data_arrays['mass'].sum() == sp.get_mass('kg')

        # all particles have been released
        assert data_arrays['positions'].shape == (sp.release.num_elements, 3)
        assert np.allclose(data_arrays['positions'][0],
                           sp.release.start_position, 0, atol=1e-10)
        assert np.allclose(data_arrays['positions'][-1],
                           sp.release.end_position, 0, atol=1e-10)

        # the delta position is a constant and is given by
        # (sp.end_position-sp.start_position)/(sp.num_elements-1)
        delta_p = ((sp.release.end_position - sp.release.start_position) /
                   (sp.release.num_elements - 1))
        # assert np.all(delta_p == sp.release.delta_pos)
        assert np.allclose(delta_p, np.diff(data_arrays['positions'], axis=0),
                           0, 1e-10)

    positions = [((128.0, 2.0, 0.), (128.0, -2.0, 0.)),     # south
                 ((128.0, 2.0, 0.), (128.0, 4.0, 0.)),      # north
                 ((128.0, 2.0, 0.), (125.0, 2.0, 0.)),      # west
                 ((-128.0, 2.0, 0.), (-120.0, 2.0, 0.)),    # east
                 ((-128.0, 2.0, 0.), (-120.0, 2.01, 0.))]   # almost east

    @pytest.mark.parametrize(('start_position', 'end_position'), positions)
    def test_cont_cardinal_direction_release(self,
                                             start_position,
                                             end_position):
        """
        testing a line release to the south, north, west, east, almost east
        - multiple elements per step
        - also start before release and end after release

        Same test as test_cont_line_release3; however, the timestep is
        fixed as opposed to variable.
        """
        self.test_cont_line_release_vary_timestep(start_position,
                                                  end_position,
                                                  vary_timestep=False)

    @pytest.mark.parametrize(('start_position', 'end_position'),
                             nom_positions)
    def test_cont_line_release_single_elem_over_multiple_timesteps(self,
                                                start_position, end_position):
        """
        testing a release that is releasing while moving over time
        - less than one elements is released per step. A single element is
          released over multiple time steps.

        Test it's right for the full release
        """
        sp = point_line_release_spill(num_elements=10,
                                      start_position=start_position,
                                      release_time=self.release_time,
                                      end_position=end_position,
                                      end_release_time=(self.release_time +
                                                        timedelta(minutes=50))
                                      )

        # start before release
        time = self.release_time - timedelta(minutes=2)
        delta_t = timedelta(minutes=2)
        timestep = delta_t.total_seconds()
        data_arrays = {}

        # end after release
        while time < sp.release.end_release_time + delta_t:
            """
            keep releasing particles - no need to use self.release_and_assert
            since computing expected_number_of_particles_released is cumbersome
            Also, other tests verify that expected number of particles are
            being released - keep this easy to understand and follow
            """
            num = sp.num_elements_to_release(time, timestep)
            data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
            sp.set_newparticle_values(num, time, timestep, data_arrays)
            time += delta_t

        assert data_arrays['positions'].shape == (sp.release.num_elements, 3)
        assert np.allclose(data_arrays['positions'][0],
                           sp.release.start_position, atol=1e-10)
        assert np.allclose(data_arrays['positions'][-1],
                           sp.release.end_position, atol=1e-10)

        # the delta position is a constant and is given by
        # (sp.end_position-sp.start_position)/(sp.num_elements-1)
        delta_p = ((sp.release.end_position - sp.release.start_position) /
                   (sp.release.num_elements - 1))
        # assert np.all(delta_p == sp.release.delta_pos)
        assert np.allclose(delta_p, np.diff(data_arrays['positions'], axis=0),
                           0, 1e-10)

    def test_cont_not_valid_times_exception(self):
        """ Check exception raised if end_release_time < release_time """
        with raises(ValueError):
            point_line_release_spill(num_elements=100,
                                     start_position=self.start_position,
                                     release_time=self.release_time,
                                     end_release_time=(self.release_time -
                                                       timedelta(seconds=1))
                                     )

    def test_end_position(self):
        """
        Define a point release since end_position is not given. Now if
        start_position is changed, the end_position is still None, unless
        user explicitly changes it. If we started out with Point release, it
        continues to be a Point release until end_position attribute is
        modified
        """
        sp = point_line_release_spill(num_elements=self.num_elements,
                                      start_position=self.start_position,
                                      release_time=self.release_time)

        assert sp.release.end_position is None

        sp.release.start_position = (0, 0, 0)
        assert np.all(sp.release.start_position == (0, 0, 0))
        assert sp.release.end_position is None

    def test_end_release_time(self):
        """
        similar to test_end_position - if end_release_time is None, user
        defined an instantaneous release and varying the release_time will
        not effect end_release_time. User must explicitly change
        end_release_time if we want to make this time varying
        """
        sp = point_line_release_spill(num_elements=self.num_elements,
                                      start_position=self.start_position,
                                      release_time=self.release_time)

        assert sp.end_release_time is None
        new_time = (self.release_time + timedelta(hours=20))

        sp.release.release_time = new_time
        assert sp.release_time == new_time
        assert sp.end_release_time is None

    @pytest.mark.parametrize(("json_", "amount", "units"),
                             [('save', 1.0, 'kg'),
                              ('webapi', 1.0, 'g'),
                              ('save', 5.0, 'l'),
                              ('webapi', 5.0, 'barrels')])
    def test_serialization_deserialization(self, json_, amount, units):
        """
        tests serializatin/deserialization of the Spill object
        """
        spill = point_line_release_spill(num_elements=self.num_elements,
                                         start_position=self.start_position,
                                         release_time=self.release_time,
                                         amount=amount,
                                         units=units)
        new_spill = Spill.deserialize(spill.serialize())
        assert new_spill == spill

""" A few more line release (point_line_release_spill) tests """
num_elems = ((998, ),
             (100, ),
             (11, ),
             (10, ),
             (5, ),
             (4, ),
             (3, ),
             (2, ))


@pytest.mark.parametrize(('num_elements', ), num_elems)
def test_single_line(num_elements):
    """
    various numbers of elemenets over ten time steps, so release
    is less than one, one and more than one per time step.
    """
    print 'using num_elements:', num_elements
    release_time = datetime(2012, 1, 1)
    end_time = release_time + timedelta(seconds=100)
    time_step = timedelta(seconds=10)
    start_pos = np.array((0., 0., 0.))
    end_pos = np.array((1.0, 2.0, 0.))

    sp = point_line_release_spill(num_elements=num_elements,
                                  start_position=start_pos,
                                  release_time=release_time,
                                  end_position=end_pos,
                                  end_release_time=end_time)

    time = release_time
    data_arrays = {}
    while time <= end_time + time_step * 2:
        # data = sp.release_elements(time, time_step.total_seconds())
        num = sp.num_elements_to_release(time, time_step.total_seconds())
        data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
        if num > 0:
            sp.set_newparticle_values(num, time, time_step.total_seconds(),
                                      data_arrays)

        time += time_step

    assert len(data_arrays['positions']) == num_elements
    assert np.allclose(data_arrays['positions'][0], start_pos)
    assert np.allclose(data_arrays['positions'][-1], end_pos)

    # all axes should release particles with same, evenly spaced delta_position
    for ix in range(3):
        assert np.allclose(data_arrays['positions'][:, ix],
                           np.linspace(start_pos[ix], end_pos[ix],
                                       num_elements))


def test_line_release_with_one_element():
    """
    one element with a line release
    -- doesn't really make sense, but it shouldn't crash
    """
    release_time = datetime(2012, 1, 1)
    end_time = release_time + timedelta(seconds=100)
    time_step = timedelta(seconds=10)
    start_pos = np.array((0., 0., 0.))
    end_pos = np.array((1.0, 2.0, 0.))

    sp = point_line_release_spill(num_elements=1,
                                  start_position=start_pos,
                                  release_time=release_time,
                                  end_position=end_pos,
                                  end_release_time=end_time)

    num = sp.num_elements_to_release(release_time, time_step.total_seconds())
    data_arrays = mock_append_data_arrays(arr_types, num)

    assert num == 1

    sp.set_newparticle_values(num, release_time, time_step.total_seconds(),
                              data_arrays)
    assert sp.num_released == 1
    assert np.array_equal(data_arrays['positions'], [start_pos])


def test_line_release_with_big_timestep():
    """
    a line release: where the timestep spans before to after the release time
    """
    release_time = datetime(2012, 1, 1)
    end_time = release_time + timedelta(seconds=100)
    time_step = timedelta(seconds=300)
    start_pos = np.array((0., 0., 0.))
    end_pos = np.array((1.0, 2.0, 0.))

    sp = point_line_release_spill(num_elements=10,
                                  start_position=start_pos,
                                  release_time=release_time,
                                  end_position=end_pos,
                                  end_release_time=end_time)

    num = sp.num_elements_to_release(release_time - timedelta(seconds=100),
                                     time_step.total_seconds())
    assert num == sp.release.num_elements

    data_arrays = mock_append_data_arrays(arr_types, num)
    sp.set_newparticle_values(num, release_time - timedelta(seconds=100),
                              time_step.total_seconds(), data_arrays)

    # all axes should release particles with same, evenly spaced delta_position
    for ix in range(3):
        assert np.allclose(data_arrays['positions'][:, ix],
                           np.linspace(start_pos[ix], end_pos[ix],
                                       sp.release.num_elements))

""" end line release (point_line_release_spill) tests"""


def release_elements(sp, release_time, time_step, data_arrays={}):
    """
    Common code for all spatial release tests
    """
    num = sp.num_elements_to_release(release_time, time_step)

    if num > 0:
        # release elements and set their initial values
        data_arrays = mock_append_data_arrays(arr_types, num, data_arrays)
        sp.set_newparticle_values(num, release_time, time_step, data_arrays)
    else:
        if data_arrays == {}:
            # initialize arrays w/ 0 elements if nothing is released
            data_arrays = mock_append_data_arrays(arr_types, 0, data_arrays)

    return (data_arrays, num)


""" conditions for SpatialRelease """


class TestSpatialRelease:
    @pytest.fixture(autouse=True)
    def setup(self, sample_spatial_release_spill):
        """
        define common use attributes here.
        rewind the model. Fixture is a function argument only for this function
        autouse means it is used by all test functions without explicitly
        stating it as a function argument
        After each test, the autouse fixture setup is called so self.sp and
        self.start_positions get defined
        """
        # if not hasattr(self, 'sp'):
        self.sp = sample_spatial_release_spill[0]
        self.start_positions = sample_spatial_release_spill[1]
        self.sp.rewind()

    def test_SpatialRelease_rewind(self):
        """ test rewind sets _state to original """
        assert self.sp.num_released == 0
        assert self.sp.release.start_time_invalid is None

    def test_SpatialRelease_0_elements(self):
        """
        if current_time + timedelta(seconds=time_step) <= self.release_time,
        then do not release any more elements
        """
        num = self.sp.num_elements_to_release(self.sp.release.release_time -
                                              timedelta(seconds=600), 600)
        assert num == 0

        self.sp.rewind()

        # first call after release_time
        num = self.sp.num_elements_to_release(self.sp.release.release_time +
                                              timedelta(seconds=1), 600)
        assert num == 0

        # still shouldn't release
        num = self.sp.num_elements_to_release(self.sp.release.release_time +
                                              timedelta(hours=1), 600)
        assert num == 0

        self.sp.rewind()

        # now it should:
        (data_arrays, num) = release_elements(self.sp,
                                              self.sp.release.release_time,
                                              600)
        assert np.alltrue(data_arrays['positions'] == self.start_positions)

    def test_SpatialRelease(self):
        """
        see if the right arrays get created
        """
        (data_arrays, num) = release_elements(self.sp,
                                              self.sp.release.release_time,
                                              600)

        assert (self.sp.num_released == self.sp.release.num_elements and
                self.sp.release.num_elements == num)
        assert np.alltrue(data_arrays['positions'] == self.start_positions)

    def test_SpatialRelease_inst_release_twice(self):
        """
        make sure they don't release elements twice
        """
        (data_arrays, num) = release_elements(self.sp,
                                              self.sp.release.release_time,
                                              600)
        assert (self.sp.num_released == self.sp.release.num_elements and
                self.sp.release.num_elements == num)

        (data_arrays, num) = release_elements(self.sp,
                                              self.sp.release.release_time +
                                              timedelta(seconds=600), 600,
                                              data_arrays)
        assert np.alltrue(data_arrays['positions'] == self.start_positions)
        assert num == 0

    def test_set_newparticle_positions(self):
        'define two spatial releases and check positions are set correctly'
        sp2 = Spill(SpatialRelease(self.sp.release.release_time,
                                   ((0, 0, 0), (0, 0, 0))))
        (data_arrays, num) = release_elements(self.sp,
                                              self.sp.release.release_time,
                                              600)
        # fixme -- should we be checking for the release inside the Spill?
        assert (self.sp.num_released == self.sp.release.num_elements and
                self.sp.release.num_elements == num)

        (data_arrays, num2) = release_elements(sp2,
                                               sp2.release.release_time,
                                               600,
                                               data_arrays)
        assert (sp2.num_released == sp2.release.num_elements and
                len(data_arrays['positions']) == num2 + num)
        assert (np.all(data_arrays['positions'][:num, :] ==
                self.sp.start_position))
        assert (np.all(data_arrays['positions'][num:, :] ==
                sp2.start_position))


class TestVerticalPlumeRelease:
    @pytest.fixture(autouse=True)
    def setup(self, sample_vertical_plume_spill):
        '''
        define common use attributes here.
        rewind the model. Fixture is a function argument only for this function
        autouse means it is used by all test functions without explicitly
        stating it as a function argument
        After each test, the autouse fixture setup is called so self.spill
        gets defined
        '''
        self.spill = sample_vertical_plume_spill
        self.spill.rewind()

    def test_rewind(self):
        ''' test rewind sets _state to original '''
        assert self.spill.num_released == 0
        assert self.spill.start_time_invalid is None

    def test_release_bounds(self):
        '''
        if current_time + timedelta(seconds=time_step) <= self.release_time,
        then do not release any more elements
        '''
        time_step = timedelta(hours=1).total_seconds()

        # before the beginning of the time range
        num = self.spill.num_elements_to_release(
                self.spill.release.release_time - timedelta(seconds=time_step),
                time_step)
        assert num == 0

        # past the end of the time range
        self.spill.rewind()
        num = self.spill.num_elements_to_release(
                self.spill.release.plume_gen.end_release_time, time_step)
        assert num == 0

    def test_num_elems(self):
        '''
        test that the specified number of elements is consistent with the
        number released across the lifetime of the source.
        '''
        time_step = timedelta(hours=1).total_seconds()
        total_elems = 0
        for off_time in range(int(-time_step),
                              int(time_step * 30),
                              int(time_step)):
            current_time = (self.spill.release.release_time +
                            timedelta(seconds=off_time))
            elems = self.spill.num_elements_to_release(current_time, time_step)
            total_elems += elems

        # this is not truly rigorous, but it passes at least for the test data
        # a more rigorous analysis of the plume generation method is in
        # experiments/model_intercomparison
        assert total_elems == 200

    def test_arrays(self):
        """
        see if the right arrays get created
        """
        time_step = timedelta(hours=1).total_seconds()
        (data_arrays, num) = release_elements(self.spill,
                                              self.spill.release.release_time,
                                              time_step)

        # These assertions are linked to the test data that we
        # are using
        assert num == 4
        assert data_arrays['positions'].shape == (4, 3)

        (data_arrays, num) = release_elements(self.spill,
                                              (self.spill.release.release_time
                                               + timedelta(seconds=time_step)),
                                              time_step,
                                              data_arrays)

        # print 'positions:', data_arrays['positions']
        assert num == 6
        assert data_arrays['positions'].shape == (10, 3)


# """
# Following test set/get windage_range and windage_persist parameters from the
# Spill object. These were removed but are put back into master branch so current
# webgnome works. These will eventually be removed
# """
# these are all the properties that tie Spill attriubtes to the underlying
# element_type, etc attributes.
def test_propeties():
    """
    NOTE: this is not longer set and get -- it's propeties instead

    set a couple of properties of release object and windages initializer to
    test that it works

    # fixme -- maybe this should be a complete test!
    """
    rel_time = datetime.now()
    spill = point_line_release_spill(10, (0, 0, 0), rel_time)

    assert spill.num_elements == 10
    assert spill.release_time == rel_time

    spill.num_elements = 100
    assert spill.num_elements == 100

    new_time1 = datetime(2014, 1, 1, 0, 0, 0)
    spill.release_time = new_time1
    assert spill.release_time == new_time1

    new_time2 = datetime(2014, 1, 1, 2, 0, 0)
    spill.end_release_time = new_time2
    assert spill.end_release_time == new_time2

    assert spill.release_duration == (new_time2 - new_time1).total_seconds()

    spill.start_position = (1, 2, 3)
    assert np.all(spill.start_position == (1, 2, 3))

    spill.end_position = (2, 2, 3)
    assert np.all(spill.end_position == (2, 2, 3))

    spill.windage_persist = -1
    assert spill.windage_persist == -1

    spill.windage_range = (0.4, 0.4)
    assert spill.windage_range == (0.4, 0.4)


def test_set_end_to_none():
        '''
        for two different spills, ensure that release_time and end_release_time
        all work, even if end_release_tiem is None.
        '''
        rel_time = datetime.now().replace(microsecond=0)
        end_time = rel_time + timedelta(hours=1)
        # (sc, wd, spread) = self.sample_sc_wd_spreading(1, rel_time)
        # sc.spills[0].end_release_time = None
        spill = point_line_release_spill(1,
                                         (0, 0, 0),
                                         rel_time,
                                         end_release_time=end_time,
                                         amount=100,
                                         units='kg',
                                         )

        print "release is", spill.release
        print spill.release.release_time
        # now change the end_release_time
        spill.end_release_time = None

        num_new_particles = 10
        current_time = rel_time
        time_step = 900
        data_arrays = {'mass': np.zeros((num_new_particles,), dtype=np.float64),
                       'positions': np.zeros((num_new_particles, 3), dtype=np.float64),
                       }
        print "release_duration:", spill.release_duration
        print "current_time:", current_time
        print "release_time:", spill.release.release_time, spill.release_time
        spill.set_newparticle_values(num_new_particles,
                                     current_time,
                                     time_step,
                                     data_arrays)

class TestInitElementsFromFile():
    nc_start_time = datetime(2011, 3, 11, 7, 0)
    time_step = timedelta(hours=24)

    @pytest.mark.parametrize("index", [None, 0, 2])
    def test_init(self, index):
        release = InitElemsFromFile(testdata['nc']['nc_output'], index=index)
        assert release.num_elements == 4000
        if index is None:
            # file contains initial condition plus 4 timesteps
            exp_rel_time = self.nc_start_time + self.time_step * 4
            assert np.all(release._init_data['age'] ==
                          self.time_step.total_seconds() * 4)
        else:
            exp_rel_time = self.nc_start_time + self.time_step * index

            assert np.all(release._init_data['age'] ==
                          self.time_step.total_seconds() * index)
        assert release.release_time == exp_rel_time

    def test_init_with_releasetime(self):
        'test release time gets set correctly'
        reltime = datetime(2014, 1, 1, 0, 0)
        release = InitElemsFromFile(testdata['nc']['nc_output'], reltime)
        assert release.num_elements == 4000
        assert release.release_time == reltime

    @pytest.mark.parametrize("at", [{},
                                    {'windages'}])
    def test_release_elements(self, at):
        'release elements in the context of a spill container'
        s = Spill(InitElemsFromFile(testdata['nc']['nc_output']))
        sc = SpillContainer()
        sc.spills += s
        sc.prepare_for_model_run(array_types=at)
        num_les = sc.release_elements(self.time_step, self.nc_start_time)
        assert sc.num_released == s.release.num_elements
        assert num_les == s.release.num_elements
        for array, val in s.release._init_data.iteritems():
            if array in sc:
                assert np.all(val == sc[array])
                assert val is not sc[array]
            else:
                assert array not in at

    def test_full_run(self):
        'just check that all data arrays work correctly'
        s = Spill(InitElemsFromFile(testdata['nc']['nc_output']))
        model = Model(start_time=s.release_time,
                      time_step=self.time_step.total_seconds(),
                      duration=timedelta(days=2)
                      )
        model.spills += s
        model.movers += RandomMover()

        # setup model run
        for step in model:
            if step['step_num'] == 0:
                continue
            for sc in model.spills.items():
                for key in sc.data_arrays.keys():
                    # following keys will not change with run
                    if key in ('status_codes',
                               'mass',
                               'init_mass',
                               'id',
                               'spill_num',
                               'last_water_positions'):  # all water map
                        assert np.all(sc[key] == s.release._init_data[key])

def test_grid_spill():

    # fixme -- needs a real test!

    bounds = ((0.0, 0.0),
              (10.0, 10.0))
    resolution = 20
    release_time = datetime(2017, 10, 20, 12)
    spill = grid_spill(bounds,
                       resolution,
                       release_time
                       )
                       # substance=None,
                       # amount=None,
                       # units=None,
                       # windage_range=(.01, .04),
                       # windage_persist=900,
                       # name='Surface Grid Spill'
                       # )
    print spill

    assert spill.num_elements == resolution * resolution
    print vars(spill)

    # assert False




if __name__ == '__main__':

    # TC = Test_PointSourceSurfaceRelease()
    # TC.test_model_skips_over_release_time()

    test_line_release_with_big_timestep()
