"""
tamoc_spill.py

This file contains the definitions to create a TAMOC simulation in GNOME and
run the simulation in a seemless integration with GNOME.

"""

from gnome.spill.release import Release
from gnome.spill.spill import SpillSchema
from gnome.utilities.time_utils import asdatetime
from gnome.gnomeobject import GnomeId
from gnome import _valid_units

import numpy as np

class TamocSpill(GnomeId):
    """
    Models a TAMOC spill by combining the near-field model with Release 
    and Substance objects
    
    """
    _schema = SpillSchema
    valid_vol_units = _valid_units('Volume')
    valid_mass_units = _valid_units('Mass')
    
    def __init__(self, 
                 on=True, 
                 num_elements=1000,
                 amount=0.,
                 units='bbl/d',
                 substance=None,
                 release=None,
                 water=None,
                 gor=None,
                 d0=0.,
                 phi_0=-np.pi/2.,
                 theta_0=0.,
                 amount_uncertainty_scale=0.0,
                 **kwargs):
        
        super(TamocSpill, self).__init__(**kwargs)
        
        self.on = on
        self.substance = substance
        self.release = release
        num_elements = release.num_elements
        self.num_elements = num_elements
        
        self.units = units
        self.amount = amount
        
        self.water = water
        
        self.amount_uncertainty_scale = amount_uncertainty_scale
        self.frac_coverage = 1.0
        self._num_released = 0
        

class WellBlowoutRelease(Release):
    """
    The primary source class for Lagrangian elements
    
    The primary source class that releases Lagrangian elements from a TAMOC
    oil well blowout spill scenario.  
    
    
    """
    def __init__(self,
                 release_time=None,
                 start_position=None,
                 num_elements=None,
                 num_per_timestep=None,
                 end_release_time=None,
                 end_position=None,
                 release_mass=0,
                 **kwargs):
        
        # Initialize internal element counters to None
        self._num_elements = self._num_per_timestep = None
        
        # Ensure either the number of elements or the release rate is given
        if num_elements is None and num_per_timestep is None:
            num_elements = 1000
        
        # Pass variables on toward inherited objects
        super(WellBlowoutRelease, self).__init__(release_time=release_time,
                                                 num_elements=num_elements,
                                                 release_mass = release_mass,
                                                 **kwargs)
        
        # Error check whether the number of elements is over specified
        if num_elements is not None and num_per_timestep is not None:
            msg = ('Either num_elements released or a release rate,'
                   'defined by num_per_timestep must be given, not both')
            raise TypeError(msg)
        
        # Update the internal counter for element release rate
        self._num_per_timestep = num_per_timestep
        
        # Initialize remaining input variables
        self.end_release_time = asdatetime(end_release_time)
        self.start_position = start_position
        self.end_position = end_position

def well_blowout(num_elements,
                 start_position, 
                 release_time, 
                 end_release_time=None,
                 water=None,
                 substance='AD01554',
                 on=True,
                 amount=0.,
                 units='bbl/d',
                 gor=0.,
                 d0=0.,
                 phi_0=-np.pi / 2.,
                 theta_0=0.,
                 windage_range=(0.01, 0.04),
                 windage_persist=900,
                 name='Oil Well Blowout'):
    """
    Helper function returns a Spill object containing a well blowout
    
    Uses the TAMOC model to simulate the near-field of a well blowout and
    passes Lagrangian Elements to GNOME, providing seamless integration
    with GNOME.
    
    Parameters
    ----------
    num_elements : int
        Total number of Lagrangian elements to release in GNOME for this
        spill (--)
    start_position : tup
        Initial position (lat, lon, z) in (deg, deg, m) for the blowout
        release.  Here, z is positive down so that z is depth.
    release_time : datetime
        State time for this blowout release
    end_release_time : datetime
        End time for this blowout release
    substance : Gnome Oil
        Type of oil released from the blowout.  Normally, this would be an
        Adios ID number for an oil in the GNOME Oil Library.
    on : bool
        Flag indicating that this spill object is currently active
    amount : float
        Flow rate of the release at standard conditions (bbl/d)
    units : str
        Units for the amount attribute
    gor : float
        Gas-to-oil ratio of the release at standard conditions (std ft^3/bbl)
    d0 : float
        Diameter of the equivalent circular area of the orifice at the 
        release (m)
    phi_0 : float
        Vertical orientation of the release relative to the horizontal plane
        (rad). Since z is positive down, a vertical release would have 
        phi_0 = -np.pi/2.
    theta_0 : float
        Horizontal orientation of the release relative to the x-axis (East) 
        in (rad); positive angles are counter-clockwise from East.  For a 
        vertical release, this parameter has no effect.
    windage_range : tup
        Minimum and maximum windage coefficient values stored in a tuple (--)
    windage_persist : int
        ???
    name : str
        Name for this spill
    
    Returns
    -------
    ts : gnome.spill.spill.Spill
        A gnome.spill.spill.Spill object that integrates seamlessly with 
        the GNOME simulation environment.  This object determines 1.) when
        and how many Lagrangian elements to create and 2.) specifies the 
        initial properties of these Lagrangian elements.
    
    Notes
    -----
    This function is based on the gnome.spill.spill.point_line_release_spill
    function in the py_gnome package.
    
    """
    # Create the release object
    release = WellBlowoutRelease(release_time=release_time,
                                 start_position=start_position,
                                 num_elements=num_elements,
                                 end_release_time=end_release_time,
                                 )
    
    # Create the spill object, which includes the release
    ts = TamocSpill(release=release,
                    water=water,
                    substance=substance,
                    amount=amount,
                    units=units,
                    gor=gor,
                    d0=d0,
                    phi_0=phi_0,
                    theta_0=theta_0,
                    name=name,
                    on=on)
    
    # Make sure that is the substance is None, the model will not break
    if substance is None:
        ts.substance.windage_range=windage_range
        ts.substance.windage_persist=windage_persist
    
    return ts
    