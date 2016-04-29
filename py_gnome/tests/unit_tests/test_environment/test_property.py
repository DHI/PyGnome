import os
import pytest
import datetime as dt
import numpy as np
import pysgrid
import datetime
from gnome.environment.property import Time
from gnome.environment.grid_property import GriddedProp, GridVectorProp
from gnome.environment.ts_property import TimeSeriesProp, TSVectorProp
from gnome.environment.property_classes import VelocityTS, VelocityGrid
from gnome.utilities.remote_data import get_datafile
import netCDF4 as nc
import unit_conversion

base_dir = os.path.dirname(__file__)
'''
Need to hook this up to existing test data infrastructure
'''

s_data = os.path.join(base_dir, 'sample_data')
curr_dir = os.path.join(s_data, 'currents')
curr_file = get_datafile(os.path.join(curr_dir,'tbofs_example.nc'))
dataset = nc.Dataset(curr_file)
node_lon = dataset['lonc']
node_lat = dataset['latc']
grid_u = dataset['water_u']
grid_v = dataset['water_v']
grid_time = dataset['time']
test_grid = pysgrid.SGrid(node_lon=node_lon,
                          node_lat=node_lat)


dates = np.array([dt.datetime(2000, 1, 1, 0),
                  dt.datetime(2000, 1, 1, 2),
                  dt.datetime(2000, 1, 1, 4)])
dates2 = np.array([dt.datetime(2000, 1, 1, 0),
                   dt.datetime(2000, 1, 1, 2),
                   dt.datetime(2000, 1, 1, 4),
                   dt.datetime(2000, 1, 1, 6),
                   dt.datetime(2000, 1, 1, 8), ])
uv_units = 'm/s'
u_data = np.array([2., 4., 6., 8., 10.])
v_data = np.array([5., 7., 9., 11., 13.])

s_data = np.array([20,30,40])


@pytest.fixture()
def ts():
    return Time(dates2, extrapolate=False)

class TestTime:

    def test_extrapolation(self, ts):
        ts.extrapolate = True
        before = dt.datetime(1999,12,31,23)
        after = dt.datetime(2000,1,1,9)
        assert ts.index_of(before) == 0
        assert ts.index_of(after) == 5
        assert ts.index_of(ts.time[-1]) == 4
        assert ts.index_of(ts.time[0]) == 0
        ts.extrapolate = False
        with pytest.raises(ValueError):
            ts.index_of(before)
        with pytest.raises(ValueError):
            ts.index_of(after)
        assert ts.index_of(ts.time[-1]) == 4
        assert ts.index_of(ts.time[0]) == 0


@pytest.fixture()
def u():
    return TimeSeriesProp(name='u', units='m/s', time=dates2, data=u_data)

@pytest.fixture()
def v():
    return TimeSeriesProp(name='v', units='m/s', time=dates2, data=v_data)

@pytest.fixture()
def vp():
    return TSVectorProp(name='vp', units='m/s', time=dates2, variables=[u_data,v_data], extrapolate=False)

class TestTSprop:

    def test_construction(self):

        u = None
        v = None
        with pytest.raises(ValueError):
            # mismatched data and dates length
            u = TimeSeriesProp('u', 'm/s', dates, u_data)

        assert u is None

        u = TimeSeriesProp('u', 'm/s', dates2, u_data)

        assert u is not None
        assert u.name == 'u'
        assert u.units == 'm/s'
        assert u.time == Time(dates2)
        assert (u.data == u_data).all()

        v = None
        with pytest.raises(ValueError):
            v = TimeSeriesProp('v', 'nm/hr', dates2, v_data)

        assert v is None

    def test_unit_conversion(self,u):

        t = u.in_units('km/hr')

        assert t.data is not v_data
        assert round(t.data[0],2) == 7.2

        with pytest.raises(unit_conversion.UnitConversionError):
            # mismatched data and dates length
            t = u.in_units('nm/hr')

    def test_set_data(self,u):
        u.data = v_data
        assert (u.data == v_data).all()

        with pytest.raises(ValueError):
            # mismatched data and time length
            u.data = [5,6,7]

    def test_set_time(self,u):
        with pytest.raises(ValueError):
            # mismatched data and time length
            u.time = dates

        u.time = dates2
        assert u.time == Time(dates2)

    def test_set_attr(self,u):

        #mismatched data and time length
        with pytest.raises(ValueError):
            u.set_attr(time = dates2, data=s_data)

        u.set_attr(name = 'v')
        assert u.name == 'v'

        with pytest.raises(ValueError):
            u.set_attr(time = dates,data=u_data)

        u.set_attr(time=dates, data=s_data)
        assert u.data[0] == 20

        u.set_attr(data = [50,60,70])
        assert u.data[0] == 50

        u.set_attr(time = [datetime.datetime(2000,1,3,1),
                         datetime.datetime(2000,1,3,2),
                         datetime.datetime(2000,1,3,3)])

        u.set_attr(extrapolate=True, units='km/hr')

        assert u.extrapolate == True
        assert u.units == 'km/hr'

        with pytest.raises(ValueError):
            u.set_attr(units='nm/hr')

    def test_at(self,u):
        pts = np.array(((1,1), (2,2)))
        t1 = dt.datetime(1999, 12,31,23)
        t2 = dt.datetime(2000, 1, 1, 0)
        t3 = dt.datetime(2000, 1, 1, 1)
        t4 = dt.datetime(2000,1, 1, 8)
        t5 = dt.datetime(2000,1, 1, 9)

        #No extrapolation. out of bounds time should fail
        with pytest.raises(ValueError):
            u.at(pts, t1)
        assert (u.at(pts, t2) == np.array([2])).all()
        assert (u.at(pts, t3) == np.array([3])).all()
        assert (u.at(pts, t4) == np.array([10])).all()
        with pytest.raises(ValueError):
            u.at(pts, t5)

        #turn extrapolation on
        u.set_attr(extrapolate=True)
        print u.time
        print u.time.time
        print u.time.extrapolate
        assert (u.at(pts, t1) == np.array([2])).all()
        assert (u.at(pts, t5) == np.array([10])).all()

class TestTSVectorProp:

    def test_construction(self, u, v):
        vp = None
        vp = TSVectorProp(name='vp', units='m/s', time=dates2, variables=[u_data,v_data], extrapolate=False)

        assert all(vp.variables[0].data == u_data)

        #3 components
        vp = TSVectorProp(name='vp', units='m/s', time=dates2, variables=[u_data,v_data, u_data], extrapolate=False)

        #Using TimeSeriesProp
        vp = TSVectorProp(name='vp', variables=[u, v])
        assert vp.time == vp.variables[0].time == vp.variables[1].time

        #Mixed TSP/raw variables
        with pytest.raises(TypeError):
            vp = TSVectorProp(name='vp', variables=[u, v_data])

        #SHORT TIME
        with pytest.raises(ValueError):
            vp = TSVectorProp(name='vp', units='m/s', time=dates, variables=[u_data,v_data], extrapolate=False)

        #DIFFERENT LENGTH VARS
        with pytest.raises(ValueError):
            vp = TSVectorProp(name='vp', units='m/s', time=dates2, variables=[s_data,v_data], extrapolate=False)

        #UNSUPPORTED UNITS
        with pytest.raises(ValueError):
            vp = TSVectorProp(name='vp', units='km/s', time=dates2, variables=[s_data,v_data, u_data], extrapolate=False)

    def test_unit_conversion(self, vp):
        nvp = vp.in_units('km/hr')
        assert round(nvp.variables[0].data[0],2) == 7.2

        with pytest.raises(unit_conversion.UnitConversionError):
            # mismatched data and dates length
            nvp = vp.in_units('nm/hr')

        assert nvp != vp
        assert all(nvp.variables[0].data != vp.variables[0].data)

    def test_set_variables(self,vp):
        print u_data
        vp.variables = [u_data,v_data,u_data]
        assert (vp._variables[0].data == u_data).all()

        with pytest.raises(ValueError):
            # mismatched data and time length
            vp.variables = [[5],[6],[7]]

    def test_set_time(self,vp):
        with pytest.raises(ValueError):
            # mismatched data and time length
            vp.time = dates

        vp.time = dates2
        assert vp.time == Time(dates2)

    def test_set_attr(self,vp):

        #mismatched data and time length
        with pytest.raises(ValueError):
            vp.set_attr(time = dates2, variables=[s_data, s_data])

        vp.set_attr(name = 'vp1')
        assert vp.name == 'vp1'

        with pytest.raises(ValueError):
            vp.set_attr(time = dates, variables=[u_data,v_data])

        vp.set_attr(time=dates, variables=[s_data, s_data])
        assert vp.variables[0].data[0] == 20

        vp.set_attr(variables = [[50,60,70],s_data])
        assert vp.variables[0].data[0] == 50

        vp.set_attr(time = [datetime.datetime(2000,1,3,1),
                         datetime.datetime(2000,1,3,2),
                         datetime.datetime(2000,1,3,3)])

        vp.set_attr(extrapolate=True, units='km/hr')

        assert vp.extrapolate == True
        assert [v.extrapolate == True for v in vp._variables]
        assert vp.units == 'km/hr'

        with pytest.raises(ValueError):
            vp.set_attr(units='nm/hr')

    def test_at(self,vp):
        pts = np.array(((1,1), (2,2)))
        t1 = dt.datetime(1999, 12,31,23)
        t2 = dt.datetime(2000, 1, 1, 0)
        t3 = dt.datetime(2000, 1, 1, 1)
        t4 = dt.datetime(2000,1, 1, 8)
        t5 = dt.datetime(2000,1, 1, 9)

        #No extrapolation. out of bounds time should fail
        with pytest.raises(ValueError):
            vp.at(pts, t1)

        print vp.name
        assert (vp.at(pts, t2) == np.array([2,5])).all()
        assert (vp.at(pts, t3) == np.array([3,6])).all()
        assert (vp.at(pts, t4) == np.array([10,13])).all()
        with pytest.raises(ValueError):
            vp.at(pts, t5)

        #turn extrapolation on
        vp.set_attr(extrapolate=True)
        print vp.time
        print vp.time.time
        print vp.time.extrapolate
        assert (vp.at(pts, t1) == np.array([2,5])).all()
        assert (vp.at(pts, t5) == np.array([10,13])).all()


@pytest.fixture()
def gp():
    return GriddedProp(name='u', units='m/s', time=grid_time, data=grid_u, data_file=curr_file, grid=test_grid, grid_file=curr_file)

@pytest.fixture()
def gp2():
    return GriddedProp(name='v;', units='m/s', time=grid_time, data=grid_v, data_file=curr_file, grid=test_grid, grid_file=curr_file)

@pytest.fixture()
def gvp():
    return GridVectorProp(name='velocity', units='m/s', time=grid_time, variables = [gp(), gp2()])

class TestGriddedProp:

    def test_construction(self):

        u = GriddedProp(name='u',
                        units='m/s',
                        data=grid_u,
                        grid=test_grid,
                        time=grid_time,
                        data_file='tbofs_example.nc',
                        grid_file='tbofs_example.nc')
        with pytest.raises(ValueError):
            u = GriddedProp(name='u',
                            units='m/s',
                            data=None, #NO DATA
                            grid=test_grid,
                            time=grid_time,
                            data_file='tbofs_example.nc',
                            grid_file='tbofs_example.nc')
        with pytest.raises(ValueError):
            u = GriddedProp(name='u',
                            units='m/s',
                            data=grid_u,
                            grid=None, #NO GRID
                            time=grid_time,
                            data_file='tbofs_example.nc',
                            grid_file='tbofs_example.nc')
        with pytest.raises(ValueError):
            u = GriddedProp(name='u',
                            units='m/s',
                            data=u_data, #BAD DATA SHAPE
                            grid=test_grid,
                            time=grid_time,
                            data_file='tbofs_example.nc',
                            grid_file='tbofs_example.nc')
        with pytest.raises(ValueError):
            u = GriddedProp(name='u',
                            units='m/s',
                            data=grid_u,
                            grid=test_grid,
                            time=dates2, #BAD TIME SHAPE
                            data_file='tbofs_example.nc',
                            grid_file='tbofs_example.nc')

    def test_unit_conversion(self, gp):
        with pytest.raises(AttributeError):
            gp.units = 'km/hr'

    def test_set_data(self,gp):
        with pytest.raises(AttributeError):
            gp.data = grid_v

    def test_set_grid(self,gp):
        with pytest.raises(AttributeError):
            gp.grid = test_grid

    def test_set_time(self, gp):
        gp.time = grid_time
        gt2 = gp.time.time.copy()
        gt2[0] = datetime.datetime(1999, 12, 31, 23)
        gp.time = gt2
        assert gp.time.time[0] == datetime.datetime(1999, 12, 31, 23)

    def test_set_attr(self, gp):
        gp.set_attr(name = 'gridpropobj')
        assert gp.name == 'gridpropobj'

        gp.set_attr(extrapolate = True)
        assert gp.extrapolate == True
        assert gp.time.extrapolate == True

        gp.set_attr(data = grid_v)
        assert gp.data == grid_v

        gp.set_attr(grid = test_grid)
        assert gp.grid == test_grid
        assert gp.grid.infer_grid(gp.data) == 'node'

        gp.set_attr(data = grid_u, grid = test_grid)
        assert gp.data == grid_u
        assert gp.grid.infer_grid(gp.data) == 'node'

        gp.set_attr(data_file = 'f', grid_file = 'f')
        assert gp.data_file == 'f'

    def test_at(self, gp):
        print gp.time.time
        print gp.at(np.array([-82.8, 27.475]), gp.time.time[2])
        assert gp.at(np.array([-82.8, 27.475]), gp.time.time[2]) != 0
        assert np.isnan(gp.at(np.array([0,0]), gp.time.time[2]))

class TestGridVectorProp:

    def test_construction(self, gp, gp2):
        #Grid_file and data_file missing
        with pytest.raises(ValueError):
            gvp = GridVectorProp(name='velocity', units='m/s', time=grid_time, variables = [grid_u, grid_v])
        #Units inconsistent with variables units
        with pytest.raises(ValueError):
            gvp = GridVectorProp(name='velocity', units='km/hr', time=grid_time, variables = [gp,gp2])
        gvp = GridVectorProp(name='velocity', units='m/s', time=grid_time, variables = [gp,gp2])
        assert gvp.name == 'velocity'
        assert gvp.units == 'm/s'
        assert gvp.time == Time(grid_time)
        assert gvp._variables[0].data == grid_u
        assert gvp._variables[0].name == 'u'


@pytest.fixture()
def vel(u,v):
    return VelocityTS(name='vel', variables=[u,v])
class TestVelocityTS:
    def test_construction(self, u, v):
        vel = None
        vel = VelocityTS(name='vel', units='m/s', time=dates2, variables=[u_data,v_data], extrapolate=False)

        assert all(vel.variables[0].data == u_data)

        #Using TimeSeriesProp objects
        vel = VelocityTS(name='vel', variables=[u, v])
        assert vel.time == vel.variables[0].time == vel.variables[1].time
        #3 components
        with pytest.raises(ValueError):
            vel = VelocityTS(name='vel', units='m/s', time=dates2, variables=[u_data,v_data, u_data], extrapolate=False)

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_serialization(self, vel, json_):
        dict_ = vel.serialize(json_)
        print dict_
        assert dict_[u'name'] == 'vel'
        if json_ == 'webapi':
            assert dict_[u'units'] == ('m/s', 'degrees')
            assert dict_[u'varnames'] == ['magnitude', 'direction', 'u', 'v']
        if json_ == 'save':
            print dict_['timeseries']
            assert dict_['timeseries'][0][1][0] == 2.0
            assert dict_[u'units'] == ['m/s']

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_deserialize(self, vel, json_):
        dict_ = vel.serialize(json_)
        dser = VelocityTS.deserialize(dict_)
        print dser
        assert dser['name'] == 'vel'
        assert all(dser['time'] == dates2)
        assert all(np.isclose(dser['data'][0],u_data))

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_new_from_dict(self, vel, json_):
        deser = VelocityTS.deserialize(vel.serialize(json_))
        vel2 = VelocityTS.new_from_dict(deser)
        assert vel == vel2

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_update_from_dict(self, vel, json_):
        deser = VelocityTS.deserialize(vel.serialize(json_))
        vel2 = VelocityTS.new_from_dict(deser)
        deser['name'] = 'vel2'
        vel.update_from_dict(deser)
        vel2.name = 'vel2'
        assert vel.name == 'vel2'
        assert vel == vel2


@pytest.fixture()
def g_vel(gp,gp2):
    return VelocityGrid(name='g_vel', variables=[gp, gp2])
class TestVelocityGrid:
    def test_construction(self, gp, gp2):
        g_vel = VelocityGrid(name='g_vel', variables=[gp,gp2])
        g_vel = VelocityGrid(name='g_vel', units='m/s', time=grid_time, grid=test_grid, variables=[grid_u, grid_v], grid_file=curr_file, data_file=curr_file)
        pass

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_serialization(self, g_vel, json_):
        dict_ = g_vel.serialize()

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_deserialize(self, g_vel, json_):
        pass

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_new_from_dict(self, g_vel, json_):
        pass

    @pytest.mark.parametrize("json_", ('save', 'webapi'))
    def test_update_from_dict(self, g_vel, json_):
        pass


if __name__ == "__main__":
    import pprint
    k = vp()
    pts = np.array(((1,1), (2,2)))
    t1 = dt.datetime(1999, 12,31,23)
    t2 = dt.datetime(2000, 1, 1, 0)
    t3 = dt.datetime(2000, 1, 1, 1)
    t4 = dt.datetime(2000,1, 1, 8)
    t5 = dt.datetime(2000,1, 1, 9)

    #No extrapolation. out of bounds time should fail
    with pytest.raises(ValueError):
        k.at(pts, t1)

    print k.name
    assert (k.at(pts, t2) == np.array([2,5])).all()
    assert (k.at(pts, t3) == np.array([3,6])).all()
    assert (k.at(pts, t4) == np.array([10,13])).all()
    with pytest.raises(ValueError):
        k.at(pts, t5)

    v = g_vel(gp(), gp2())
    dict_ = v.serialize()
    pp.pprint(dict_)
    deser = VelocityGrid.deserialize(dict_)
    pp.pprint(deser)
    v2 = VelocityGrid.new_from_dict(deser)
    v == v2
    test_tsprop_construction()
    test_tsprop_unit_conversion()
    test_tsprop_set_attr()
    test_gridprop_construction()
