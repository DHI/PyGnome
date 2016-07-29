﻿'''
model biodegradation process
'''
import numpy as np

from gnome.utilities.serializable import Serializable

from .core import WeathererSchema
from gnome.weatherers import Weatherer

from gnome.array_types import (mass, 
                               droplet_avg_size)

from math import exp, pi

class Biodegradation(Weatherer, Serializable):
    _state = copy.deepcopy(Weatherer._state)
    _state += [Field('water', save=True, update=True, save_reference=True),
               Field('waves', save=True, update=True, save_reference=True)]

    _schema = WeathererSchema

    def __init__(self, waves=None, water=None, **kwargs):
        self.waves = waves
        self.water = water

        super(Biodegradation, self).__init__(**kwargs)

        self.array_types.update({'area': area,
                                 'mass':  mass,
                                 'droplet_avg_size': droplet_avg_size
                                 })


    def prepare_for_model_run(self, sc):
        '''
            Add biodegradation key to mass_balance if it doesn't exist.
            - Assumes all spills have the same type of oil
            - let's only define this the first time
        '''
        if self.on:
            super(Biodegradation, self).prepare_for_model_run(sc)
            sc.mass_balance['bio_degradation'] = 0.0

    def prepare_for_model_step(self, sc, time_step, model_time):
        '''
            Set/update arrays used by dispersion module for this timestep
        '''
        super(Biodegradation, self).prepare_for_model_step(sc, time_step, model_time)

        if not self.active:
            return


    def bio_degradate_oil(self, data, substance, **kwargs):
        '''
            1. Droplet distribution per LE should be calculated by the natural
            dispersion process and saved in the data arrays before the 
            biodegradation weathering process.
            2. It must take into consideration saturates and aromatic mass fractions only.
        '''

        model_time = kwargs.get('model_time')
        time_step = kwargs.get('time_step')

        comp_masses = data['mass_components']
        droplet_avg_sizes = data['droplet_avg_size']

        # we are going to calculate bio degradation rate coefficients (K_comp_rate) 
        # just for saturate and aromatics components - other ones are masked to 0.0

        K_comp_rates = get_K_comp_rates(substance)

        mass_biodegradated = comp_masses * exp(-4.0 * pi * droplet_avg_sizes ** 2 * 
                                               K_comp_rate * time_step / 
                                               comp_masses.sum(axes=1))

        # TODO

    def get_K_comp_rates(self, substance, temperature):
        '''
            Calculate bio degradation rate coefficients
            We calculate ones just for saturate and aromatics components
            Also they are coming for two environment conditions - 
            water temperature (temperature parameter)
             1) Temperate conditions - 6 deg C and above
             2) Arctic conditions - below 6 deg C
            And they are defined by pseudo component boiling point (K)
        '''

        k_rate = [0.128807242,      # arctic conditions, saturate components
                 0.941386396,       # temperate conditions, saturate components
                 [0.126982603,      # arctic conditions, aromatic components, BP < 630K
                  0.021054707],     # arctic conditions, aromatic components, BP >= 630K
                 [0.575541103,      # temperate conditions, aromatic components, BP < 630K
                  0.084840485]]     # temperate conditions, aromatic components, BP >= 630K

        cond = temperature < 6  # 0 - arctic, 1 - temperate

        comp = {
            'Saturates': 0,
            'Aromatics': 1
            }.get(substance._sara['type'], 2)

        # TODO

    def weather_elements(self, sc, time_step, model_time):
        '''
            weather elements over time_step
        '''
        if not self.active:
            return

        if sc.num_released == 0:
            return

        for substance, data in sc.itersubstancedata(self.array_types):
            if len(data['mass']) is 0:
                continue

            bio_deg = self.bio_degradate_oil(model_time=model_time,
                                             time_step=time_step,
                                             data=data,
                                             substance=substance)

            data['mass_components'] -= bio_deg

            sc.mass_balance['bio_degradation'] += bio_deg.sum()

            data['mass'] = data['mass_components'].sum(1)

            # log bio degradated amount
            self.logger.debug('{0} Amount bio degradated for {1}: {2}'
                              .format(self._pid,
                                      substance.name,
                                      sc.mass_balance['bio_degradation']))

        sc.update_from_fatedataview()


    def serialize(self, json_='webapi'):
        """
            'water'/'waves' property is saved as references in save file
        """
        toserial = self.to_serialize(json_)
        schema = self.__class__._schema()
        serial = schema.serialize(toserial)

        if json_ == 'webapi':
            if self.waves:
                serial['waves'] = self.waves.serialize(json_)
            if self.water:
                serial['water'] = self.water.serialize(json_)

        return serial

    @classmethod
    def deserialize(cls, json_):
        """
            Append correct schema for water
        """
        if not cls.is_sparse(json_):
            schema = cls._schema()
            dict_ = schema.deserialize(json_)

            if 'water' in json_:
                obj = json_['water']['obj_type']
                dict_['water'] = (eval(obj).deserialize(json_['water']))

            if 'waves' in json_:
                obj = json_['waves']['obj_type']
                dict_['waves'] = (eval(obj).deserialize(json_['waves']))

            return dict_
        else:
            return json_