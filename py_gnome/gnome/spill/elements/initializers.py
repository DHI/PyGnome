#!/usr/bin/env python
'''
Types of elements that a spill can expect
These are properties that are spill specific like:
  'floating' element_types would contain windage_range, windage_persist
  'subsurface_dist' element_types would contain rise velocity distribution info
  'nonweathering' element_types would set use_droplet_size flag to False
  'weathering' element_types would use droplet_size, densities, mass?
'''
import copy
import numpy as np

from colander import SchemaNode, Int, Float, Range, TupleSchema

from gnome.utilities.rand import random_with_persistance

from gnome.cy_gnome.cy_rise_velocity_mover import rise_velocity_from_drop_size

from gnome.persist import base_schema
from gnome.gnomeobject import GnomeId
from gnome.persist.base_schema import GeneralGnomeObjectSchema
from gnome.utilities.distributions import (NormalDistributionSchema,
                                           WeibullDistributionSchema,
                                           LogNormalDistributionSchema,
                                           UniformDistributionSchema)
"""
Initializers for various element types
"""

class InitBaseClass(GnomeId):
    """
    All Init* classes will define the _state attribute, so just do so in a
    base class.

    It also documents that all initializers must implement an initialize method

    """

    def __init__(self, *args, **kwargs):
        # Contains the array_types that are set by an initializer but defined
        # anywhere else. For example, InitRiseVelFromDropletSizeFromDist()
        # computes droplet_diameter in the data_arrays even though it isn't
        # required by the mover. SpillContainer queries all initializers so it
        # knows about these array_types and can include them.
        # Make it a set since ElementType does a membership check in
        # set_newparticle_values()
        self.array_types = set()
        super(InitBaseClass, self).__init__(*args,**kwargs)

    def initialize(self, num_new_particles, spill, data_arrays, substance):
        """
        all classes that derive from Base class must implement initialize
        method
        """
        pass


class WindageSchema(TupleSchema):
    min_windage = SchemaNode(Float(), validator=Range(0, 1.0),
                             default=0.01)
    max_windage = SchemaNode(Float(), validator=Range(0, 1.0),
                             default=0.04)


class InitWindagesSchema(base_schema.ObjTypeSchema):
    """
    windages initializer values
    """
    windage_range = WindageSchema(
        save=True, update=True,
    )
    windage_persist = SchemaNode(
        Int(), default=900, save=True, update=True,
    )


class InitWindages(InitBaseClass):
    _schema = InitWindagesSchema

    def __init__(self, windage_range=(0.01, 0.04), windage_persist=900, name='windages', *args, **kwargs):
        """
        Initializes the windages, windage_range, windage_persist data arrays.
        Initial values for windages use infinite persistence. These are updated
        by the WindMover for particles with non-zero persistence.

        Optional arguments:

        :param windage_range=(0.01, 0.04): the windage range of the elements
            default is (0.01, 0.04) from 1% to 4%.
        :type windage_range: tuple: (min, max)

        :param windage_persist=-1: Default is 900s, so windage is updated every
            900 sec. -1 means the persistence is infinite so it is only set at
            the beginning of the run.
        :type windage_persist: integer seconds
        """
        super(InitWindages, self).__init__(*args, **kwargs)
        self.windage_persist = windage_persist
        self.windage_range = windage_range
        self.array_types.update(('windages',
                                 'windage_range',
                                 'windage_persist'))
        self.name = name

    def __repr__(self):
        return ('{0.__class__.__module__}.{0.__class__.__name__}('
                'windage_range={0.windage_range}, '
                'windage_persist={0.windage_persist}'
                ')'.format(self))

    def to_dict(self, json_=None):
        return InitBaseClass.to_dict(self, json_=json_)

    @property
    def windage_persist(self):
        return self._windage_persist

    @windage_persist.setter
    def windage_persist(self, val):
        if val == 0:
            raise ValueError("'windage_persist' cannot be 0. "
                             "For infinite windage, windage_persist=-1 "
                             "otherwise windage_persist > 0.")
        self._windage_persist = val

    @property
    def windage_range(self):
        return self._windage_range

    @windage_range.setter
    def windage_range(self, val):
        if np.any(np.asarray(val) < 0) or np.asarray(val).size != 2:
            raise ValueError("'windage_range' >= (0, 0). "
                             "Nominal values vary between 1% to 4%. "
                             "Default windage_range=(0.01, 0.04)")
        self._windage_range = val

    def initialize(self, num_new_particles, spill, data_arrays,
                   substance=None):
        """
        Since windages exists in data_arrays, so must windage_range and
        windage_persist if this initializer is used/called
        """
        (data_arrays['windage_range'][-num_new_particles:, 0],
         data_arrays['windage_range'][-num_new_particles:, 1],
         data_arrays['windage_persist'][-num_new_particles:]) = \
            (self.windage_range[0],
             self.windage_range[1],
             self.windage_persist)

        # initialize all windages - ignore persistence during initialization
        # if we have infinite persistence, these values are never updated
        random_with_persistance(
                    data_arrays['windage_range'][-num_new_particles:][:, 0],
                    data_arrays['windage_range'][-num_new_particles:][:, 1],
                    data_arrays['windages'][-num_new_particles:])


# do following two classes work for a time release spill?


class InitMassFromPlume(InitBaseClass):
    """
    Initialize the 'mass' array based on mass flux from the plume spilled
    """
    _schema = base_schema.ObjTypeSchema

    def __init__(self):
        """
        update array_types
        """
        super(InitMassFromPlume, self).__init__()
        self.array_types.add('mass')
        self.name = 'mass'

    def initialize(self, num_new_particles, spill, data_arrays, substance):
        if spill.plume_gen is None:
            raise ValueError('plume_gen attribute of spill is None - cannot'
                             ' compute mass without plume mass flux')

        data_arrays['mass'][-num_new_particles:] = \
            spill.plume_gen.mass_of_an_le * 1000


class DistributionBaseSchema(base_schema.ObjTypeSchema):
    'Add schema to base class since all derived classes use same schema'

    distribution = GeneralGnomeObjectSchema(
        acceptable_schemas=[UniformDistributionSchema,
                          NormalDistributionSchema,
                          WeibullDistributionSchema,
                          LogNormalDistributionSchema],
        save=True, update=True
    )


class DistributionBase(InitBaseClass):
    '''
    Define a base class for all initializers that contain a distribution.
    Keep the code to serialize/deserialize distribution objects here so we only
    have to write it once.
    '''
    _schema = DistributionBaseSchema


class InitRiseVelFromDist(DistributionBase):

    def __init__(self, distribution=None, **kwargs):
        """
        Set the rise velocity parameters to be sampled from a distribution.

        :param distribution: An object capable of generating a probability
                             distribution.
        :type distribution:
            Right now, we have:
             * UniformDistribution
             * NormalDistribution
             * LogNormalDistribution
             * WeibullDistribution
            New distribution classes could be made.  The only
            requirement is they need to have a set_values()
            method which accepts a NumPy array.
            (presumably, this function will also modify
             the array in some way)
        """
        super(InitRiseVelFromDist, self).__init__(**kwargs)

        if distribution:
            self.distribution = distribution
        else:
            raise TypeError('InitRiseVelFromDist requires a distribution for '
                            'rise velocities')

        self.array_types.add('rise_vel')
        self.name = 'rise_vel'

    def initialize(self, num_new_particles, spill, data_arrays,
                   substance=None):
        'Update values of "rise_vel" data array for new particles'
        self.distribution.set_values(
                            data_arrays['rise_vel'][-num_new_particles:])


class InitRiseVelFromDropletSizeFromDist(DistributionBase):

    def __init__(self, distribution=None,
                 water_density=1020.0, water_viscosity=1.0e-6,
                 **kwargs):
        """
        Set the droplet size from a distribution. Use the C++ get_rise_velocity
        function exposed via cython (rise_velocity_from_drop_size) to obtain
        rise_velocity from droplet size. Even though the droplet size is not
        changing over time, it is still stored in data array, as it can be
        useful for post-processing (called 'droplet_diameter')

        :param distribution: An object capable of generating a probability
                             distribution.
        :type distribution:
        Right now, we have:
         * UniformDistribution
         * NormalDistribution
         * LogNormalDistribution
         * WeibullDistribution
        New distribution classes could be made.  The only
        requirement is they need to have a set_values()
        method which accepts a NumPy array.
        (presumably, this function will also modify
         the array in some way)
        :param water_density: 1020.0 [kg/m3]
        :type water_density: float
        :param water_viscosity: 1.0e-6 [m^2/s]
        :type water_viscosity: float
        """
        super(InitRiseVelFromDropletSizeFromDist, self).__init__(**kwargs)

        if distribution:
            self.distribution = distribution
        else:
            raise TypeError('InitRiseVelFromDropletSizeFromDist requires a '
                            'distribution for droplet sizes')

        self.water_viscosity = water_viscosity
        self.water_density = water_density
        self.array_types.update(('rise_vel', 'droplet_diameter'))
        self.name = 'rise_vel'

    def initialize(self, num_new_particles, spill, data_arrays, substance):
        """
        Update values of 'rise_vel' and 'droplet_diameter' data arrays for
        new particles. First create a droplet_size array sampled from specified
        distribution, then use the cython wrapped (C++) function to set the
        'rise_vel' based on droplet size and properties like LE_density,
        water density and water_viscosity:
        gnome.cy_gnome.cy_rise_velocity_mover.rise_velocity_from_drop_size()
        """
        drop_size = np.zeros((num_new_particles, ), dtype=np.float64)
        le_density = np.zeros((num_new_particles, ), dtype=np.float64)

        self.distribution.set_values(drop_size)

        data_arrays['droplet_diameter'][-num_new_particles:] = drop_size

        # Don't require a water object
        # water_temp = spill.water.get('temperature')
        # le_density[:] = substance.density_at_temp(water_temp)

        if spill.water is not None:
            water_temp = spill.water.get('temperature')
            le_density[:] = substance.density_at_temp(water_temp)
        else:
            le_density[:] = substance.density_at_temp()

        # now update rise_vel with droplet size - dummy for now
        rise_velocity_from_drop_size(
                                data_arrays['rise_vel'][-num_new_particles:],
                                le_density, drop_size,
                                self.water_viscosity, self.water_density)
