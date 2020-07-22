Spills
======

Using helper functions
----------------------

Setting up the spill class can be tricky because it requires both a release object and an element_type. More
details on setting up the Spill object can be found below, but for a lot of typical use cases helper functions in 
the scripting package can be utilized. Examples include:

Surface spill 
~~~~~~~~~~~~~

We use the :func:`gnome.scripting.surface_point_line_spill` helper function to inialize a release along a line 
that occurs over one day. The oil type is specified as an Alaskan Crude from the ADIOS database with a spill volume 
of 5000 barrels. Here we change the default windage range to be 1-2% with an infinite persistence (particles keep 
the same windage value for all time).
::

    from gnome.model import Model
    from gnome.scripting import surface_point_line_spill
    from datetime import datetime, timedelta
    start_time = datetime(2015, 1, 1, 0, 0)
    model = Model(start_time=start_time,
              duration=timedelta(days=3),
              time_step=60 * 15, #seconds
              )
    spill = surface_point_line_spill(num_elements=1000,
                                 start_position=(-144,48.5, -1000.0),
                                 release_time=start_time,
                                 end_position=(-144,48.6, 0.0),
                                 end_release_time= start_time + timedelta(days=1),
                                 amount=5000,
                                 substance='ALASKA NORTH SLOPE (MIDDLE PIPELINE)',
                                 units='bbl',
                                 windage_range=(0.01,0.02),
                                 windage_persist=-1,
                                 name='My spill')
    model.spills += spill
    
    # ... add movers/weatherers
    
    model.full_run()
    
.. _subsurface_plume:

Subsurface plume
~~~~~~~~~~~~~~~~

For initialization of a subsurface plume, we can use the subsurface_plume_spill helper function.
Required parameters in this case also include a specification of the droplet size distribution 
or of the rise velocities. The :mod:`gnome.utilities.distributions` module includes methods for 
specifying different types of distributions. In this case we specify a uniform distribution of
droplets ranging from 10-300 microns::
    
    from gnome.scripting import subsurface_plume_spill
    from gnome.utilities.distributions import UniformDistribution
    ud = UniformDistribution(10e-6,300e-6) #droplets in the range 10-300 microns
    spill = subsurface_plume_spill(num_elements=1000,
                                   start_position=(-144,48.5, 0.0),
                                   release_time=start_time,
                                   distribution=ud,
                                   distribution_type='droplet_size',
                                   end_release_time= start_time + timedelta(days=1),
                                   amount=5000,
                                   substance='ALASKA NORTH SLOPE (MIDDLE PIPELINE)',
                                   units='bbl',
                                   windage_range=(0.01,0.02),
                                   windage_persist=-1,
                                   name='My spill')
                                   
    
The Spill Class
---------------

Spills in GNOME contain a release object which specifies the details of the release 
(e.g. where, when, how many elements). They also contain an element_type object which
provides information on the type of substance spilled (e.g. floating oil, subsurface plume etc). 
If element_type is not specified then the default is a conservative floating substance. The 
default for floating substances is to have windage values set in the range 1-4% with a persistence of
15 minutes.

For example, in the scripting :doc:`scripting_intro` we showed how to setup a spill for a conservative substance using
the PointLineRelease class::

    from gnome.model import Model
    from gnome.spill import PointLineRelease, Spill
    from datetime import datetime, timedelta
    start_time = datetime(2015, 1, 1, 0, 0)
    model = Model(start_time=start_time,
                  duration=timedelta(days=3),
                  time_step=60 * 15, #seconds
                  )
    release = PointLineRelease(release_time=start_time,start_position=(-144,48.5,0),num_elements=1000)
    spill = Spill(release)
    model.spills += spill
    
To specify the spill to represent a specific oil from the ADIOS database and specify the amount spilled, we could instantiate the Spill oject like this::
    
    from gnome.spill.elements import ElementType
    element_type=ElementType(substance='ALASKA NORTH SLOPE (MIDDLE PIPELINE)')
    spill = Spill(release,element_type=element_type,amount=5000,units='bbls')
    model.spills += spill
    
Or even simpler::

    spill = Spill(release,substance='ALASKA NORTH SLOPE (MIDDLE PIPELINE)',amount=5000,units='bbls')

In this last case, the Spill class instantiates the element_type based on the specified substance.
    
