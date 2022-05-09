nc_names = {'grid_temperature' : {'default_names': ['water_t', 'temp'], 'cf_names': ['sea_water_temperature', 'sea_surface_temperature']},
            'grid_salinity' : {'default_names': ['salt'], 'cf_names': ['sea_water_salinity', 'sea_surface_salinity']},
            'grid_sediment' : {'default_names': ['sand_06']},
            'ice_concentration' : {'default_names': ['ice_fraction', 'aice' ], 'cf_names': ['sea_ice_area_fraction']},
            'bathymetry' : {'default_names': ['h'], 'cf_names': ['depth']},
            'grid_current' : {'default_names': {'u': ['u', 'U', 'water_u', 'curr_ucmp', 'u_surface', 'u_sur'],
                                                'v': ['v', 'V', 'water_v', 'curr_vcmp', 'v_surface', 'v_sur'],
                                                'w': ['w', 'W']}, 
                              'cf_names': {'u': ['eastward_sea_water_velocity', 'surface_eastward_sea_water_velocity'],
                                           'v': ['northward_sea_water_velocity', 'surface_northward_sea_water_velocity'],
                                           'w': ['upward_sea_water_velocity']}},
            'grid_wind' : {'default_names': {'u': ['air_u', 'Air_U', 'air_ucmp', 'wind_u'],
                                             'v': ['air_v', 'Air_V', 'air_vcmp', 'wind_v']}, 
                           'cf_names': {'u': ['eastward_wind', 'eastward wind'],
                                        'v': ['northward_wind', 'northward wind']}},
            'ice_velocity' : {'default_names': {'u': ['ice_u','uice'], 'v': ['ice_v','vice']}, 
                              'cf_names': {'u': ['eastward_sea_ice_velocity'],
                                           'v': ['northward_sea_ice_velocity']}},                  
            }

                