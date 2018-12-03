#!/usr/bin/env python
"""
Script to test GNOME with:

TAMOC - Texas A&M Oilspill Calculator

https://github.com/socolofs/tamoc

This is a very simpile environment:

Simple map (no land) and simple current mover (steady uniform current)

Rise velocity and vertical diffusion

But it's enough to see if the coupling with TAMOC works.

"""


import os
import numpy as np
from datetime import datetime, timedelta

from gnome import scripting
from gnome.spill.elements import plume
from gnome.utilities.distributions import WeibullDistribution
from gnome.environment.gridded_objects_base import Variable, Time, Grid_S
from gnome.environment import GridCurrent

from gnome.model import Model
from gnome.map import GnomeMap
from gnome.spill import point_line_release_spill
from gnome.scripting import subsurface_plume_spill
from gnome.movers import (RandomMover,
                          TamocRiseVelocityMover,
                          RandomVerticalMover,
                          SimpleMover,
                          PyCurrentMover)

from gnome.outputters import Renderer
from gnome.outputters import NetCDFOutput
from gnome.tamoc import tamoc_spill

# define base directory
base_dir = os.path.dirname(__file__)

x, y = np.mgrid[-30:30:61j, -30:30:61j]
y = np.ascontiguousarray(y.T)
x = np.ascontiguousarray(x.T)
# y += np.sin(x) / 1
# x += np.sin(x) / 5
g = Grid_S(node_lon=x,
          node_lat=y)
g.build_celltree()
t = Time.constant_time()
angs = -np.arctan2(y, x)
mag = np.sqrt(x ** 2 + y ** 2)
vx = np.cos(angs) * mag
vy = np.sin(angs) * mag
vx = vx[np.newaxis, :] * 5
vy = vy[np.newaxis, :] * 5

vels_x = Variable(name='v_x', units='m/s', time=t, grid=g, data=vx)
vels_y = Variable(name='v_y', units='m/s', time=t, grid=g, data=vy)
vg = GridCurrent(variables=[vels_y, vels_x], time=t, grid=g, units='m/s')


def make_model(images_dir=os.path.join(base_dir, 'images')):
    print 'initializing the model'

    # set up the modeling environment
    start_time = datetime(2004, 12, 31, 13, 0)
    model = Model(start_time=start_time,
                  duration=timedelta(days=3),
                  time_step=30 * 60,
                  uncertain=False)

    print 'adding the map'
    model.map = GnomeMap()  # this is a "water world -- no land anywhere"

    # renderere is only top-down view on 2d -- but it's something
    renderer = Renderer(output_dir=images_dir,
                        image_size=(1024, 768),
                        output_timestep=timedelta(hours=1),
                        )
    renderer.viewport = ((-.15, -.35), (.15, .35))

    print 'adding outputters'
    model.outputters += renderer

    # Also going to write the results out to a netcdf file
    netcdf_file = os.path.join(base_dir, 'script_plume.nc')
    scripting.remove_netcdf(netcdf_file)

    model.outputters += NetCDFOutput(netcdf_file,
                                     which_data='most',
                                     # output most of the data associated with the elements
                                     output_timestep=timedelta(hours=2))

    print "adding Horizontal and Vertical diffusion"

    # Horizontal Diffusion
    # model.movers += RandomMover(diffusion_coef=5)
    # vertical diffusion (different above and below the mixed layer)
    model.movers += RandomVerticalMover(vertical_diffusion_coef_above_ml=5,
                                        vertical_diffusion_coef_below_ml=.11,
                                        mixed_layer_depth=10)

    print 'adding Rise Velocity'
    # droplets rise as a function of their density and radius
    model.movers += TamocRiseVelocityMover()

    print 'adding a circular current and eastward current'
    # This is .3 m/s south
    model.movers += PyCurrentMover(current=vg,
                                       default_num_method='RK2',
                                       extrapolate=True)
    model.movers += SimpleMover(velocity=(0., -0.1, 0.))

    # Now to add in the TAMOC "spill"
    print "Adding TAMOC spill"

    model.spills += tamoc_spill.TamocSpill(release_time=start_time,
                                           start_position=(0, 0, 1000),
                                           num_elements=1000,
                                           end_release_time=start_time + timedelta(days=1),
                                           name='TAMOC plume',
                                           TAMOC_interval=None,  # how often to re-run TAMOC
                                           )

    return model


if __name__ == "__main__":
    scripting.make_images_dir()
    model = make_model()
    print "about to start running the model"
    for step in model:
        if step['step_num'] == 23:
            print 'running tamoc again'
            import pdb
            pdb.set_trace()
            sp = model.spills[0]
#            sp.tamoc_parameters['release_phi'] = -np.pi / 4
#            sp.tamoc_parameters['release_theta'] = -np.pi
            sp.tamoc_parameters['ua'] = np.array([-0.05, -0.05])
#            sp.tamoc_parameters['va'] = np.array([-1, -0.5, 0])
#            sp.tamoc_parameters['wa'] = np.array([0.01, 0.01, 0.01])
#            sp.tamoc_parameters['depths'] = np.array([0., 1000., 2000])
            sp.droplets, sp.diss_components = sp._run_tamoc()
        if step['step_num'] == 25:
            sp = model.spills[0]
            sp.tamoc_parameters['ua'] = np.array([0.05, 0.05])
            sp.droplets, sp.diss_components = sp._run_tamoc()
        print step
        # model.
