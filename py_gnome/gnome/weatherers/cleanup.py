'''
oil removal from various cleanup options
add these as weatherers
'''
from datetime import timedelta
import copy

import numpy as np
from colander import (SchemaNode, Float, String, drop, Range)

from gnome.basic_types import oil_status, fate as bt_fate
from gnome.weatherers import Weatherer
from gnome.environment.wind import WindSchema
from gnome.environment import Waves

from .core import WeathererSchema
from .. import _valid_units

import unit_conversion as uc
from gnome.environment.water import WaterSchema
from gnome.persist.base_schema import GeneralGnomeObjectSchema
from gnome.environment.gridded_objects_base import VectorVariableSchema
from gnome.movers.movers import ProcessSchema
from gnome.environment.waves import WavesSchema
from gnome.persist.extend_colander import LocalDateTime
from gnome.persist.validators import convertible_to_seconds


class RemoveMass(object):
    '''
    create a mixin for mass removal. These methods are used by CleanUpBase and
    also by manual_beaching.
    '''
    # todo: following is same as Spill code so rework to make it DRY
    valid_vol_units = _valid_units('Volume')
    valid_mass_units = _valid_units('Mass')

    def _get_mass(self, substance, amount, units):
        '''
        return 'amount' in units of 'kg' for specified substance
        uses the density corresponding with API temperature
        '''
        if units in self.valid_mass_units:
            rm_mass = uc.convert('Mass', units, 'kg', amount)
        else:
            # amount must be in volume units
            water_temp = self.water.get('temperature')
            rho = substance.density_at_temp(water_temp)
            rm_vol = uc.convert('Volume', units, 'm^3', amount)

            rm_mass = rho * rm_vol

        return rm_mass

    def _set__timestep(self, time_step, model_time):
        '''
        For cleanup operations we may know the start time pretty precisely.
        Use this to set _timestep to less than time_step resolution. Mostly
        done for testing right now so if XXX amount is skimmed between
        active_start and active_stop, the rate * duration gives the correct
        amount. Object must be active before invoking this, else
        self._timestep will give invalid results
        '''
        if not self.active:
            return

        self._timestep = time_step
        dt = timedelta(seconds=time_step)

        if (model_time < self.active_start):
            self._timestep = \
                time_step - (self.active_start -
                             model_time).total_seconds()

        if (self.active_stop < model_time + dt):
            self._timestep = (self.active_stop -
                              model_time).total_seconds()

    def prepare_for_model_step(self, sc, time_step, model_time):
        '''
        Do sub timestep resolution here so numbers add up correctly
        Mark LEs to be skimmed - do them in order right now. Assume all LEs
        that are released together will be skimmed together since they would
        be closer to each other in position.

        Assumes: there is more mass in water than amount of mass to be
        skimmed. The LEs marked for Skimming are marked only once -
        code checks to see if any LEs are marked for skimming and if
        none are found, it marks them.
        '''
        if not self.on:
            self._active = False
            return

        if (model_time + timedelta(seconds=time_step) > self.active_start and
                self.active_stop > model_time):
            self._active = True
        else:
            self._active = False

        self._set__timestep(time_step, model_time)


class CleanUpBase(RemoveMass, Weatherer):
    '''
    Just need to add a few internal methods for Skimmer + Burn common code
    Currently defined as a base class.
    '''
    def __init__(self, **kwargs):
        '''
        add 'frac_water' to array_types and pass **kwargs to base class
        __init__ using super
        '''
        self._efficiency = None
        self.efficiency = kwargs.pop("efficiency", 1.0)

        super(CleanUpBase, self).__init__(**kwargs)

        self.array_types.update({'frac_water'})

    @property
    def efficiency(self):
        return self._efficiency

    @efficiency.setter
    def efficiency(self, value):
        '''
            Update efficiency.

            - Efficiency can be None since it indicates that we use wind
              to compute efficiency.
            - If efficiency is not None, it must be a number greater than
              or equal to 0.0 and less than or equal to 1.0.
        '''
        if value is None:
            self._efficiency = value
        else:
            valid = np.logical_and(value >= 0, value <= 1)
            self._efficiency = np.where(valid, value, self._efficiency).astype('float')

    def _get_substance(self, sc):
        '''
        return a single substance - cleanup operations only know about the
        total amount removed. Unclear how to assign this to multiple substances
        For now, just log an error if more than one substance present
        '''
        substance = sc.get_substances(complete=False)
        if len(substance) > 1:
            self.logger.error('Found more than one type of Oil '
                              '- not supported. Results will be incorrect')
        return substance[0]

    def _update_LE_status_codes(self,
                                sc,
                                new_status,
                                substance,
                                mass_to_remove,
                                oilwater_mix=True):
        '''
        Need to mark LEs to 'new_status'. It updates the 'fate_status' for
        'surface_weather' LEs. Mark LEs based on mass.
        Mass to remove is assumed to be the oil/water mixture by default
        (oilwater_mix=True) so we need to find the oil_amount given the
        water_frac:

            volume = sc['mass']/API_density
            (1 - sc['frac_water']) * oil_water_vol = volume
            oil_water_vol = volume / (1 - sc['frac_water'])

        Now, do a cumsum of oil_water_mass and find where
            np.cumsum(oil_water_vol) >= vol_to_remove
        and change the status_codes of these LEs. Can just as easily multiple
        everything by API_density to get
            np.cumsum(oil_water_mass) >= mass_to_remove
            mass_to_remove = sc['mass'] / (1 - sc['frac_water'])
        This is why the input is 'mass_to_remove' instead of 'vol_to_remove'
        - less computation

        Note: For ChemicalDispersion, the mass_to_remove is not the mass of the
            oil/water mixture, but the mass of the oil. Use the oilwater_mix
            flag to indicate this is the case.
        '''
        arrays = {'fate_status', 'mass', 'frac_water'}
        data = sc.substancefatedata(substance, arrays, 'surface_weather')
        curr_mass = data['mass']

        if oilwater_mix:
            # create a mass array of oil/water mixture and use this when
            # marking LEs for removal
            curr_mass = curr_mass / (1 - data['frac_water'])

        # (1 - frac_water) * mass_to_remove
        if mass_to_remove >= curr_mass.sum():
            data['fate_status'][:] = new_status

            self.logger.warning('{0} insufficient mass released for cleanup'
                                .format(self._pid))
            self.logger.warning('{0} marked ALL ({1}) LEs, total mass: {2}'
                                .format(self._pid,
                                        len(data['fate_status']),
                                        data['mass'].sum()))
        else:
            # sum up mass until threshold is reached, find index where
            # total_mass_removed is reached or exceeded
            ix = np.where(np.cumsum(curr_mass) >= mass_to_remove)[0][0]
            # change status for elements upto and including 'ix'
            data['fate_status'][:ix + 1] = new_status

            self.logger.debug('{0} marked {1} LEs with mass: {2}'
                              .format(self._pid, ix, data['mass'][:ix].sum()))

        sc.update_from_fatedataview(substance, 'surface_weather')

    def _avg_frac_oil(self, data):
        '''
        find weighted average of frac_water array, return (1 - avg_frac_water)
        since we want the average fraction of oil in this data
        '''
        if data['mass'].sum() > 0:
            avg_frac_water = ((data['mass'] * data['frac_water']).
                              sum())/data['mass'].sum()
        else:
            avg_frac_water = 0
            self.logger.warning('{0} set avg_frac_water = ({1}), '
                                'total mass: {2}'
                                .format(self._pid,
                                        avg_frac_water,
                                        data['mass'].sum()))

        return (1 - avg_frac_water)


class SkimmerSchema(WeathererSchema):
    amount = SchemaNode(
        Float(), save=True, update=True
    )
    units = SchemaNode(
        String(), save=True, update=True
    )
    efficiency = SchemaNode(
        Float(), save=True, update=True
    )
    water = WaterSchema(
        missing=drop, save=True, update=True, save_reference=True
    )


class Skimmer(CleanUpBase):

    _schema = SkimmerSchema

    def __init__(self,
                 amount,
                 units,
                 efficiency,
                 active_start,
                 active_stop,
                 water=None,
                 **kwargs):
        '''
        initialize Skimmer object - calls base class __init__ using super()
        active_start and active_stop time are required
        cleanup operations must have a valid datetime - cannot use -inf and inf
        active_start/active_stop is used to get the mass removal rate
        '''
        self.water = water

        super(Skimmer, self).__init__(active_start=active_start,
                                      active_stop=active_stop,
                                      efficiency=efficiency,
                                      **kwargs)
        self._units = None
        self.amount = amount
        self.units = units

        # get the rate as amount/sec, use this to compute amount at each step
        # set in prepare_for_model_run()
        self._rate = None

        # let prepare_for_model_step set timestep to use when active_start or
        # active_stop is between a timestep. Generally don't do subtimestep
        # resolution; however, in this case we want numbers to add up correctly
        self._timestep = 0.0

        if self.units is None:
            raise TypeError('Need valid mass or volume units for amount')

    def _validunits(self, value):
        'checks if units are either valid_vol_units or valid_mass_units'
        if value in self.valid_vol_units or value in self.valid_mass_units:
            return True
        return False

    @property
    def units(self):
        'return units for amount skimmed'
        return self._units

    @units.setter
    def units(self, value):
        if self._validunits(value):
            self._units = value
        else:
            self.logger.warn('{0} are not valid volume or mass units. '
                             'Not updated'
                             .format(value))

    def prepare_for_model_run(self, sc):
        '''
        no need to call base class since no new array_types were added
        '''
        self._rate = self.amount/(self.active_stop -
                                  self.active_start).total_seconds()
        if self.on:
            sc.mass_balance['skimmed'] = 0.0

    def prepare_for_model_step(self, sc, time_step, model_time):
        '''
        Do sub timestep resolution here so numbers add up correctly
        Mark LEs to be skimmed - do them in order right now. Assume all LEs
        that are released together will be skimmed together since they would
        be closer to each other in position.

        Assumes: there is more mass in water than amount of mass to be
        skimmed. The LEs marked for Skimming are marked only once -
        code checks to see if any LEs are marked for skimming and if
        none are found, it marks them.
        '''
        super(Skimmer, self).prepare_for_model_step(sc, time_step, model_time)
        if not self.active:
            return

        # if active, setup timestep correctly
        if (sc['fate_status'] == bt_fate.skim).sum() == 0:
            substance = self._get_substance(sc)
            total_mass_removed = (self._get_mass(substance, self.amount,
                                                 self.units) *
                                  self.efficiency)

            self._update_LE_status_codes(sc,
                                         bt_fate.skim | bt_fate.surface_weather,
                                         substance, total_mass_removed)

    def _mass_to_remove(self, substance):
        '''
        use density at 15C, ie corresponding with API to do mass/volume
        conversion
        '''
        amount = self._rate * self._timestep
        rm_mass = self._get_mass(substance, amount, self.units)

        return rm_mass

    def weather_elements(self, sc, time_step, model_time):
        '''
        Assumes there is only ever 1 substance being modeled!
        remove mass equally from LEs marked to be skimmed
        '''
        if not self.active:
            return

        if len(sc) == 0:
            return

        for substance, data in sc.itersubstancedata(self.array_types,
                                                    fate='skim'):
            if len(data['mass']) is 0:
                continue

            rm_amount = self._rate * self._avg_frac_oil(data) * self._timestep
            rm_mass = self._get_mass(substance,
                                     rm_amount,
                                     self.units) * self.efficiency

            total_mass = data['mass'].sum()
            rm_mass_frac = min(rm_mass / total_mass, 1.0)
            rm_mass = rm_mass_frac * total_mass

            # if elements are also evaporating following could be true
            # need to include weathering for skimmed particles, then test and
            # add if following is required.
            # if rm_mass_frac > 1:
            #     rm_mass_frac = 1.0

            data['mass_components'] = \
                (1 - rm_mass_frac) * data['mass_components']
            data['mass'] = data['mass_components'].sum(1)

            sc.mass_balance['skimmed'] += rm_mass
            self.logger.debug('{0} amount skimmed for {1}: {2}'
                              .format(self._pid, substance.name, rm_mass))

        sc.update_from_fatedataview(fate='skim')


class BurnSchema(WeathererSchema):
    area = SchemaNode(
        Float(), save=True, update=True
    )
    thickness = SchemaNode(
        Float(), save=True, update=True
    )
    area_units = SchemaNode(
        String(), save=True, update=True
    )
    thickness_units = SchemaNode(
        String(), save=True, update=True
    )
    _oilwater_thickness = SchemaNode(
        Float(), missing=drop, save=True, update=True
    )
    _oilwater_thick_burnrate = SchemaNode(
        Float(), missing=drop, save=True, update=True
    )
    _oil_vol_burnrate = SchemaNode(
        Float(), missing=drop, save=True, update=True
    )
    efficiency = SchemaNode(
        Float(), missing=drop, save=True, update=True
    )
    wind = GeneralGnomeObjectSchema(
        acceptable_schemas=[WindSchema, VectorVariableSchema],
        missing=drop, save=True, update=True, save_reference=True
    )
    water = WaterSchema(
        missing=drop, save=True, update=True, save_reference=True
    )
    active_stop = SchemaNode(
        LocalDateTime(),
        missing=drop, validator=convertible_to_seconds,
        save=False, update=True
    )


class Burn(CleanUpBase):
    _schema = BurnSchema

    # save active_stop once burn duration is known - not update able but is
    # returned in webapi json_ so make it readable

    valid_area_units = _valid_units('Area')
    valid_length_units = _valid_units('Length')

    def __init__(self,
                 area,
                 thickness,
                 active_start,
                 area_units='m^2',
                 thickness_units='m',
                 efficiency=1.0,
                 wind=None,
                 water=None,
                 **kwargs):
        '''
        Set the area of boomed oil to be burned.
        Cleanup operations must have a valid datetime for active_start,
        cannot use -inf. Cannot set active_stop - burn automatically stops
        when oil/water thickness reaches 2mm.

        :param float area: area of boomed oil/water mixture to burn
        :param float thickness: thickness of boomed oil/water mixture
        :param datetime active_start: time when the burn starts
        :param str area_units: default is 'm^2'
        :param str thickness_units: default is 'm'
        :param float efficiency: burn efficiency, must be greater than 0 and
            less than or equal to 1.0
        :param wind: gnome.environment.Wind object. Only used to set
            efficiency if efficiency is None. Efficiency is defined as:
            1 - 0.07 * wind.get_value(model_time)
            where wind.get_value(model_time) is value of wind at model_time

        Kwargs passed onto base class:

        :param str name: name of object
        :param bool on: whether object is on or not for the run

        '''
        if 'active_stop' in kwargs:
            # user cannot set 'active_stop'
            kwargs.pop('active_stop')

        super(Burn, self).__init__(active_start=active_start,
                                   efficiency=efficiency,
                                   **kwargs)

        # initialize user units to valid units - setters following this will
        # initialize area_units and thickness_units per input values
        self._area_units = 'm^2'
        self._thickness_units = 'm'

        # thickness of burned/boomed oil which is updated at each timestep
        # this will be set once we figure out how much oil will be burned
        # in prepare_for_model_step()
        self._oilwater_thickness = None  # in SI units
        self._min_thickness = 0.002      # stop burn threshold in SI 2mm

        # following are set once LEs are marked for burn
        self._burn_constant = 0.000058
        self._oilwater_thick_burnrate = None
        self._oil_vol_burnrate = None   # burn rate of only the oil

        # validate user units before setting _area_units/_thickness_units
        self._thickness = thickness
        self.area = area

        # setters will validate the units
        self.area_units = area_units
        self.thickness_units = thickness_units
        self.wind = wind
        self.water = water

        # initialize rates and active_stop based on frac_water = 0.0
        self._init_rate_duration()

    @property
    def area_units(self):
        return self._area_units

    @area_units.setter
    def area_units(self, value):
        '''
        value must be one of the valid units given in valid_area_units
        '''
        if value not in self.valid_area_units:
            e = uc.InvalidUnitError((value, 'Area'))
            self.logger.error(e.message)
            raise e
        else:
            self._area_units = value

    @property
    def active_start(self):
        return self._active_start

    @active_start.setter
    def active_start(self, value):
        self._active_start = value
        self._init_rate_duration()

    @property
    def thickness(self):
        return self._thickness

    @thickness.setter
    def thickness(self, value):
        '''
        1. log a warning if thickness in SI units is less than _min_thickness
        2. if thickness changes, invoke _init_rate_duration() to reset
           active_stop - more important for UI so it reflects the correct
           duration.
        '''
        self._thickness = value
        self._log_thickness_warning()
        self._init_rate_duration()

    def _log_thickness_warning(self):
        '''
        when thickness or thickness_units are updated, check to see that the
        value in SI units is > _min_thickness. If it is not, then log a
        warning
        '''
        if (uc.Convert('Length', self.thickness_units, 'm',
                       self.thickness) <= self._min_thickness):
            msg = ("thickness of {0} {1}, is less than min required {2} m."
                   " Burn will not occur"
                   .format(self.thickness,
                           self.thickness_units,
                           self._min_thickness))
            self.logger.warning(msg)

    @property
    def thickness_units(self):
        return self._thickness_units

    @thickness_units.setter
    def thickness_units(self, value):
        '''
        value must be one of the valid units given in valid_length_units
        also reset active_stop()
        '''
        if value not in self.valid_length_units:
            e = uc.InvalidUnitError((value, 'Length'))
            self.logger.error(e.message)
            raise e

        self._thickness_units = value
        self._init_rate_duration()

        # if thickness in these units is < min required, log a warning
        self._log_thickness_warning()

    def prepare_for_model_run(self, sc):
        '''
        resets internal _oilwater_thickness variable to initial thickness
        specified by user and active_stop to 'inf' again.
        initializes sc.mass_balance['burned'] = 0.0
        '''
        self._init_rate_duration()

        if self.on:
            sc.mass_balance['burned'] = 0.0

    def prepare_for_model_step(self, sc, time_step, model_time):
        '''
        1. set 'active' flag based on active_start, and model_time
        2. Mark LEs to be burned - do them in order right now. Assume all LEs
           that are released together will be burned together since they would
           be closer to each other in position.
           Assumes: there is more mass in water than amount of mass to be
           burned. The LEs marked for Burning are marked only once -
           during the very first step that the object becomes active
        '''
        super(Burn, self).prepare_for_model_step(sc, time_step, model_time)
        if not self.active:
            return

        # if initial oilwater_thickness is < _min_thickness, then stop
        # don't want to deal with active_start being equal to active_stop, need
        # this incase user sets a bad initial value
        if self._oilwater_thickness <= self._min_thickness:
            self._active = False
            return

        # only when it is active, update the status codes
        if (sc['fate_status'] == bt_fate.burn).sum() == 0:
            substance = self._get_substance(sc)

            _si_area = uc.Convert('Area', self.area_units, 'm^2', self.area)
            _si_thickness = uc.Convert('Length', self.thickness_units, 'm',
                                       self.thickness)

            mass_to_remove = (self.efficiency *
                              self._get_mass(substance,
                                             _si_area * _si_thickness, 'm^3'))

            self._update_LE_status_codes(sc, bt_fate.burn,
                                         substance, mass_to_remove)

            self._set_burn_params(sc, substance)

            # set timestep after active stop is set
            self._set__timestep(time_step, model_time)

    def _init_rate_duration(self, avg_frac_oil=1):
        '''
        burn duration based on avg_frac_oil content for LEs marked for burn
        __init__ invokes this to initialize all parameters assuming
        frac_water = 0.0
        '''
        # burn rate constant is defined as a thickness rate in m/sec
        _si_area = uc.Convert('Area', self.area_units, 'm^2', self.area)

        # rate if efficiency is 100 %
        self._oilwater_thick_burnrate = self._burn_constant * avg_frac_oil
        self._oil_vol_burnrate = (self._burn_constant *
                                  avg_frac_oil ** 2 *
                                  _si_area)

        # burn duration is known once rate is known
        # reset current thickness to initial thickness whenever model is rerun
        self._oilwater_thickness = uc.Convert('Length',
                                              self.thickness_units, 'm',
                                              self.thickness)

        burn_duration = ((self._oilwater_thickness - self._min_thickness) /
                         self._oilwater_thick_burnrate)

        self.active_stop = (self.active_start +
                            timedelta(seconds=burn_duration))

    def _set_burn_params(self, sc, substance):
        '''
        Once LEs are marked for burn, the frac_water does not change
        set burn rate for oil/water thickness, as well as volume burn rate for
        oil:

        If data contains LEs marked for burning, then:

            avg_frac_oil = mass_weighed_avg(1 - data['frac_water'])
            _oilwater_thick_burnrate = 0.000058 * avg_frac_oil
            _oil_vol_burnrate = _oilwater_thick_burnrate * avg_frac_oil * area

        The burn duration is also known if efficiency is constant. However, if
        efficiency is based on variable wind, then duration cannot be computed.
        '''
        # once LEs are marked for burn, they do not weather. The
        # frac_water content will not change - let's find total_mass_rm,
        # burn_duration and rate since that is now known
        data = sc.substancefatedata(substance, {'mass', 'frac_water'},
                                    'burn')
        avg_frac_oil = self._avg_frac_oil(data)
        self._init_rate_duration(avg_frac_oil)

    def _set_efficiency(self, points, model_time):
        '''
        return burn efficiency either from efficiency attribute or computed
        from wind
        '''
        if self.efficiency is None and self.wind is None:
            self.logger.error("Set the 'efficiency' or provide 'wind' "
                              "object so efficiency can be computed. "
                              "Else using 100% efficiency")

            self.efficiency = 1.0

        if self.efficiency is None:
            # get it from wind
            ws = self.wind.get_value(points, model_time)
            self.efficiency = np.where(ws > (1. / 0.07), 0, 1 - 0.07 * ws)
            print self.efficiency

    def weather_elements(self, sc, time_step, model_time):
        '''
        1. figure out the mass to remove for current timestep based on rate and
           efficiency. Find fraction of total mass and remove equally from all
           'mass_components' of LEs marked for burning.
        2. update 'mass' array and the amount burned in mass_balance dict
        3. append to _burn_duration for each timestep
        '''
        if not self.active or len(sc) == 0:
            return

        for substance, data in sc.itersubstancedata(self.array_types, fate='burn'):
            if len(data['mass']) is 0:
                continue

            points = sc['positions']
            self._set_efficiency(points, model_time)

            # scale rate by efficiency
            # this is volume of oil burned - need to get mass from this
            vol_oil_burned = (self._oil_vol_burnrate *
                              self.efficiency *
                              self._timestep)

            rm_mass = self._get_mass(substance, vol_oil_burned, 'm^3')
            if rm_mass > data['mass'].sum():
                rm_mass = data['mass'].sum()

            rm_mass_frac = rm_mass / data['mass'].sum()

            data['mass_components'] = ((1 - rm_mass_frac) *
                                       data['mass_components'])
            data['mass'] = data['mass_components'].sum(1)

            # new thickness of oil/water mixture
            # decided not to update thickness, just use burn rate and duration
            # self._oilwater_thickness -= (self._oilwater_thick_burnrate *
            #                              self._timestep)

            sc.mass_balance['burned'] += rm_mass
            self.logger.debug('{0} amount burned for {1}: {2}'
                              .format(self._pid, substance.name, rm_mass))

        sc.update_from_fatedataview(fate='burn')


class ChemicalDispersionSchema(WeathererSchema):
    fraction_sprayed = SchemaNode(
        Float(), validator=Range(0, 1.0), save=True, update=True
    )
    efficiency = SchemaNode(
        Float(), missing=drop, validator=Range(0, 1.0),
        save=True, update=True
    )
    _rate = SchemaNode(
        Float(), missing=drop, save=True, update=True
    )
    waves = WavesSchema(
        missing=drop, save=True, update=True, save_reference=True
    )


class ChemicalDispersion(CleanUpBase):
    _schema = ChemicalDispersionSchema

    def __init__(self,
                 fraction_sprayed,
                 active_start,
                 active_stop,
                 waves=None,
                 efficiency=1.0,
                 **kwargs):
        '''
        another mass removal mechanism. The volume specified gets dispersed
        with efficiency based on wave conditions.

        :param volume: volume of oil (not oil/water?) applied with surfactant
        :type volume: float
        :param units: volume units
        :type units: str
        :param active_start: start time of operation
        :type active_start: datetime
        :param active_stop: stop time of operation
        :type active_stop: datetime
        :param waves: waves object - query to get height. It must contain
            get_value() method. Default is None to support object creation by
            WebClient before a waves object is defined
        :type waves: an object with same interface as gnome.environment.Waves

        Optional Argument: Either efficiency or waves must be set before
        running the model. If efficiency is not set, then use wave height to
        estimate an efficiency

        :param efficiency: efficiency of operation.
        :type efficiency: float between 0 and 1

        remaining kwargs include 'on' and 'name' and these are passed to base
        class via super
        '''
        super(ChemicalDispersion, self).__init__(active_start=active_start,
                                                 active_stop=active_stop,
                                                 efficiency=efficiency,
                                                 **kwargs)

        # fraction_sprayed must be > 0 and <= 1.0
        self.fraction_sprayed = fraction_sprayed
        self.waves = waves

        # rate is set the first timestep in which the object becomes active
        self._rate = None

        # fixme: this note was here: since efficiency can also be set - do not
        #        make_default_refs but we need waves!
        # we need a way to override efficiency, rather than disabling
        # default-refs but the current code sets the efficiency attribute
        # from waves.. maybe a static_efficiency property -- if it is not None,
        # then it is used, rather than any computation being made.
        self.make_default_refs = False if efficiency else True

    def prepare_for_model_run(self, sc):
        '''
        reset _rate to None. It gets set when LEs are marked to be dispersed.
        '''
        self._rate = None
        if self.on:
            sc.mass_balance['chem_dispersed'] = 0.0

    def prepare_for_model_step(self, sc, time_step, model_time):
        '''
        1. invoke base class method (using super) to set active flag
        2. mark LEs for removal
        3. set internal _rate attribute for mass removal [kg/sec]
        '''
        super(ChemicalDispersion, self).prepare_for_model_step(sc,
                                                               time_step,
                                                               model_time)
        if not self.active:
            return

        # only when it is active, update the status codes
        self._set__timestep(time_step, model_time)
        if (sc['fate_status'] == bt_fate.disperse).sum() == 0:
            substance = self._get_substance(sc)
            mass = sum([spill.get_mass() for spill in sc.spills])

            # rm_total_mass_si = mass * self.fraction_sprayed
            rm_total_mass_si = mass * self.fraction_sprayed * self.efficiency

            # the mass to remove is actual oil mass not mass of oil/water
            # mixture
            self._update_LE_status_codes(sc, bt_fate.disperse,
                                         substance, rm_total_mass_si,
                                         oilwater_mix=False)
            self._rate = \
                (rm_total_mass_si /
                 (self.active_stop - self.active_start).total_seconds())

    def _set_efficiency(self, points, model_time):
        if self.efficiency is None:
            # if wave height > 6.4 m, we get negative results - log and
            # reset to 0 if this occurs
            # can efficiency go to 0? Is there a minimum threshold?
            w = 0.3 * self.waves.get_value(points, model_time)[0]
            efficiency = (0.241 + 0.587*w - 0.191*w**2 +
                          0.02616*w**3 - 0.0016 * w**4 -
                          0.000037*w**5)
            np.clip(efficiency, 0, None)
            self.efficiency = efficiency

    def weather_elements(self, sc, time_step, model_time):
        'for now just take away 0.1% at every step'
        if self.active and len(sc) > 0:
            for substance, data in sc.itersubstancedata(self.array_types,
                                                        fate='disperse'):
                if len(data['mass']) is 0:
                    continue

                points = sc['positions']
                self._set_efficiency(points, model_time)

                # rm_mass = self._rate * self._timestep * self.efficiency
                rm_mass = self._rate * self._timestep  # rate includes efficiency

                total_mass = data['mass'].sum()
                rm_mass_frac = min(rm_mass / total_mass, 1.0)
                rm_mass = rm_mass_frac * total_mass

                data['mass_components'] = \
                    (1 - rm_mass_frac) * data['mass_components']
                data['mass'] = data['mass_components'].sum(1)

                sc.mass_balance['chem_dispersed'] += rm_mass
                self.logger.debug('{0} amount chemically dispersed for '
                                  '{1}: {2}'
                                  .format(self._pid, substance.name, rm_mass))

            sc.update_from_fatedataview(fate='disperse')
