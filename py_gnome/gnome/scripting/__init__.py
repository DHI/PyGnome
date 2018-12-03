"""
Scripting package for GNOME with assorted utilities that make it easier to
write scripts.

The ultimate goal is to be able to run py_gnome for the "common" use cases
with only functions available in this module

Helper functions are imported from various py_gnome modules
(spill, environment, movers etc).

we recommend that this module be used like so::

  import gnome.scripting import gs

Then you will have easy access to most of the stuff you need to write
py_gnome scripts with, e.g.::

    model = gs.Model(start_time="2018-04-12T12:30",
                     duration=gs.days(2),
                     time_step=gs.minutes(15))

    model.map = gs.MapFromBNA('coast.bna', refloat_halflife=0.0)  # seconds

    model.spills += gs.point_line_release_spill(num_elements=1000,
                                                start_position=(-163.75,
                                                                69.75,
                                                                0.0),
                                                release_time="2018-04-12T12:30")
"""

import gnome
from gnome.model import Model

from .utilities import (make_images_dir,
                        remove_netcdf,
                        set_verbose,
                        )

from .time_utils import (seconds,
                         minutes,
                         hours,
                         days,
                         weeks,
                         now)

from gnome.spill.spill import (point_line_release_spill,
                               surface_point_line_spill,
                               subsurface_plume_spill,
                               grid_spill,
                               )

from gnome.environment.wind import constant_wind
from gnome.movers.wind_movers import (constant_wind_mover,
                                      wind_mover_from_file,
                                      )

from gnome.environment import (IceAwareCurrent,
                               IceAwareWind,
                               )

from gnome.outputters import Renderer, NetCDFOutput, KMZOutput

from gnome.map import MapFromBNA

from gnome.environment import (GridCurrent,
                               IceAwareCurrent,
                               IceAwareWind,
                               )

from gnome.movers import (RandomMover,
                          RandomVerticalMover,
                          WindMover,
                          RiseVelocityMover,
                          PyWindMover,
                          PyCurrentMover,
                          )

from gnome.utilities.remote_data import get_datafile
