
"""
cython version of code that uses Bresenham's line algorithm to check if LEs
have crossed land on the raster map

"""

import cython

import numpy as np
from gnome.utilities.geometry.cy_point_in_polygon import points_in_poly
cimport numpy as cnp
from cpython.mem cimport PyMem_Malloc, PyMem_Free
from libc.stdint cimport int16_t, int32_t, uint8_t, uint32_t
from libc.stdlib cimport abs, div, div_t
from libcpp cimport bool

cimport type_defs

def overlap_grid(int32_t m, int32_t n, pt1, pt2):
    """
    check if the line segment from pt1 to pt could overlap the grid of
    size (m,n).

    returns True is both points are all the way to the left, right top or bottom of the grid

    This version calls the cdef version -- jsut so we do'nt ahve to do teh tuple unpacking
    of the points in the cdef version

    """
    cdef int32_t x1 = pt1[0]
    cdef int32_t y1 = pt1[1]
    cdef int32_t x2 = pt2[0]
    cdef int32_t y2 = pt2[1]

    return c_overlap_grid(m, n, x1, y1, x2, y2)

cdef int32_t c_overlap_grid(int32_t m,
                            int32_t n,
                            int32_t x1,
                            int32_t y1,
                            int32_t x2,
                            int32_t y2,
                            ):
    """
    check if the line segment from pt1 to pt could overlap the grid of
    size (m,n).

    returns 1 if both points are all the way to the left, right top or bottom of the grid

    NOTE: this could be extended to cover lines that cross quadrants, but don't intersect teh box -- wouls that be worth it?
    """
    if x1 < 0 and x2 < 0: # both left
        return 0
    elif y1 < 0 and y2 < 0: # both below
        return 0
    elif x1 >= m and x2 >= m: # both right
        return 0
    elif y1 >= n and y2 >= n: # both above
        return 0
    else:
        return 1


cdef bool c_find_first_pixel(uint8_t* grid,
                             int32_t m,
                             int32_t n,
                             int32_t x0,
                             int32_t y0,
                             int32_t x1,
                             int32_t y1,
                             int32_t *prev_x,
                             int32_t *prev_y,
                             int32_t *hit_x,
                             int32_t *hit_y,
                             ):
    """
    Marches along the grid to see if the LE movement crosses land

    returns False if no land is encountered

    returns True is a land pixel is hit.

    the passed-in values hit_x and hit_y are set to the pixel hit
    """
    cdef int32_t dx, dy, sx, sy, err, e2,
    cdef int32_t pt1_x, pt1_y, pt2_x, pt2_y
    cdef bool was_on_grid = False

    # check if totally off the grid
    if not c_overlap_grid(m, n, x0, y0, x1, y1):
        return False

    #pixels = []
    #hit_point = previous_pt = None
    #Set it up to march in the right direction depending on slope.

    dx = abs(x1-x0)
    dy = abs(y1-y0)
    if x0 < x1:
        sx = 1
    else:
        sx = -1
    if y0 < y1:
        sy = 1
    else:
        sy = -1
    err = dx-dy
    # check the first point
    if not (x0 < 0 or x0 >= m or y0 < 0 or y0 >= n):#  is the point off the grid? if so, it's not land!
        ##fixme: we should never be starting on land!
        ## should this raise an Error instead ?
        if grid[x0 * n + y0] != 0: #we've hit "land"
            prev_x[0] = x0
            prev_y[0] = y0
            hit_x[0] = x0
            hit_y[0] = y0
            return True
            #return (x0, y0), (x0, y0)
        was_on_grid = True

    while True: #keep going till hit land or the final point
        if x0 == x1 and y0 == y1:
            break
        prev_x[0] = x0
        prev_y[0] = y0
        # advance to next point
        e2 = 2*err
        if e2 > -dy:
            err = err - dy
            x0 = x0 + sx
        if e2 <  dx:
            err = err + dx
            y0 = y0 + sy

        # check for land hit
        if x0 < 0 or x0 >= m or y0 < 0 or y0 >= n:
            # is the point off the grid? if so, it's not land!
            ## if we've moved off the grid for good, no need to keep going.
            ## but can only do this if we've crossed the grid.
            if was_on_grid:
                return False
            else:
                # haven't hit the grid yet -- keep going
                continue
        else:
            if grid[x0 * n + y0] != 0:
                hit_x[0] = x0
                hit_y[0] = y0
                return True
            else:
                # there is a diagonal move -- test adjacent points also
                # but only if we're already on the grid
                if was_on_grid and (e2 > -dy) and (e2 < dx):
                    # only call it a hit if BOTH adjacent points are land.
                    pt1_x = x0
                    pt1_y = y0-sy
                    pt2_x = x0-sx
                    pt2_y = y0
                    if ( (grid[pt1_x * n + pt1_y] != 0) and #is the y-adjacent point on land?
                         (grid[pt2_x * n + pt2_y] != 0)     #is the x-adjacent point on land?
                        ):
                        hit_x[0] = pt1_x # we have to pick one -- this is arbitrary
                        hit_y[0] = pt1_y # we have to pick one -- this is arbitrary
                        #return (*prev_x, *prev_y), (*hit_x, *hit_y)
                        return True
            was_on_grid = True

    # if we get here, no hit
    return False



def find_first_pixel(grid, pt1, pt2):
    """
    This finds the first non-zero pixel that is encountered when following
    a line from pt1 to pt2.

    param: grid  -- a numpy integer array -- the raster we're working with
           zero everywhere there is not considered a "hit"
    param: pt1 -- the start point -- an integer (i, j) tuple
    param: pt2 -- the end point   -- an integer (i, j) tuple

    return: None if land is not hit
            (previous_pt, hit_point) if land is hit

    This is an adaptation of "Bresenham's line algorithm":

    (http://en.wikipedia.org/wiki/Bresenham%27s_line_algorithm)

    Usually used for drawing lines in graphics.  It's been adapted to do an
    extra check when the algorithm puts two points diagonal to each-other, so
    as to avoid an exact match with a diagonal line of land skipping through.
    If _both_ the points diagonal to the move are land, it is considered a hit.

    """

    cdef int32_t m, n
    m, n = grid.shape

    cdef int32_t  prev_x, prev_y, hit_x, hit_y

    cdef int32_t x1 = pt1[0]
    cdef int32_t y1 = pt1[1]
    cdef int32_t x2 = pt2[0]
    cdef int32_t y2 = pt2[1]

    cdef cnp.ndarray[uint8_t, ndim=2, mode="c"] grid_arr = grid
    cdef uint8_t* dataptr = &grid_arr[0,0]
    #initialize prev_x, prev_y in case point starts on land.
    prev_x = x1
    prev_y = y1

    result = c_find_first_pixel(dataptr,
                                m,
                                n,
                                x1,
                                y1,
                                x2,
                                y2,
                                &prev_x,
                                &prev_y,
                                &hit_x,
                                &hit_y,
                                )

    if result:
        return (prev_x, prev_y), (hit_x, hit_y)
    else:
        return None


## called by a method in gnome.map.RasterMap class
from gnome.basic_types import world_point_type, oil_status
@cython.boundscheck(False)
def check_land(cnp.ndarray[uint8_t, ndim=2, mode='c'] grid not None,
               cnp.ndarray[int32_t, ndim=2, mode='c'] positions not None,
               cnp.ndarray[int32_t, ndim=2, mode='c'] end_positions not None,
               cnp.ndarray[int16_t, ndim=1, mode='c'] status_codes not None,
               cnp.ndarray[int32_t, ndim=2, mode='c'] last_water_positions not None):
        """
        Do the actual land-checking

        status_codes, positions and last_water_positions are altered in place.

        NOTE: these are the integer versions -- having already have been projected to the raster coordinates
        """
        cdef int32_t  prev_x, prev_y, hit_x, hit_y
        cdef uint32_t i, num_le
        cdef int32_t m, n
        cdef bool did_hit

        num_le = positions.shape[0]
        m = grid.shape[0]
        n = grid.shape[1]

        cdef cnp.ndarray[uint8_t, ndim=2, mode="c"] grid_arr = grid
        cdef uint8_t* dataptr = &grid_arr[0,0]
        for i in range(num_le):
            if status_codes[i] == type_defs.OILSTAT_ONLAND:
                continue

            did_hit = c_find_first_pixel(dataptr,
                                         m,
                                         n,
                                         positions[i, 0],
                                         positions[i, 1],
                                         end_positions[i, 0],
                                         end_positions[i, 1],
                                         &prev_x,
                                         &prev_y,
                                         &hit_x,
                                         &hit_y,
                                         )
            if did_hit:
                last_water_positions[i, 0] = prev_x
                last_water_positions[i, 1] = prev_y
                end_positions[i,0] = hit_x
                end_positions[i,1] = hit_y
                status_codes[i] = type_defs.OILSTAT_ONLAND
            else:
                # didn't hit land -- can move the LE
                positions[i, 0] = end_positions[i, 0]
                positions[i, 1] = end_positions[i, 1]
        return None


## called by a method in gnome.map.RasterMap class
@cython.boundscheck(False)
@cython.wraparound(False)
def check_land_layers(grid_layers,
                cnp.ndarray[int32_t, ndim=1, mode='c'] grid_ratios,
                cnp.ndarray[int32_t, ndim=2, mode='c'] positions,
                cnp.ndarray[int32_t, ndim=2, mode='c'] end_positions,
                cnp.ndarray[int16_t, ndim=1, mode='c'] status_codes,
                cnp.ndarray[int32_t, ndim=2, mode='c'] last_water_positions):
        """
        Do the actual land-checking

        status_codes, positions and last_water_positions are altered in place.

        NOTE: these are the integer versions -- having already have been projected to the raster coordinates

        This version will look through multiple layers of raster map

        """
        cdef int32_t  prev_x, prev_y, hit_x, hit_y, cur_ratio, layer, coarse_pos_x, num_ratios
        cdef uint32_t i, num_le
        cdef int32_t m, n
        cdef bool did_hit
        cdef int32_t* coarse_pos = <int32_t*> PyMem_Malloc (2*sizeof(int32_t))
        cdef int32_t* coarse_end = <int32_t*> PyMem_Malloc (2*sizeof(int32_t))

        num_ratios = grid_ratios.shape[0]
        cdef uint8_t** dataptrs = <uint8_t**> PyMem_Malloc(num_ratios*sizeof(uint8_t *))
        cdef int32_t* widths = <int32_t*> PyMem_Malloc(num_ratios*sizeof(int32_t))
        cdef int32_t* heights = <int32_t*> PyMem_Malloc(num_ratios*sizeof(int32_t))

        cdef cnp.ndarray[uint8_t, ndim=2, mode="c"] grid_arr
        for i in range(num_ratios):
            grid_arr = grid_layers[i]
            widths[i] = grid_layers[i].shape[0]
            heights[i] = grid_layers[i].shape[1]
            dataptrs[i] = &grid_arr[0,0]

        num_le = positions.shape[0]

        for i in range(num_le):
            #if the LE is on land, or if it starts and ends in the same water-only square on the coarsest grid, skip this LE
            if status_codes[i] == type_defs.OILSTAT_ONLAND:
                continue

            layer = 0
            #begin the walk. If a hit is registered on the current grid, drop down one level and continue the walk.
            #If a hit is registered on the lowest level, then LE has landed.
            while True:
                coarse_pos[0] = div(positions[i,0], grid_ratios[layer]).quot
                coarse_pos[1] = div(positions[i,1], grid_ratios[layer]).quot
                coarse_end[0] = div(end_positions[i,0], grid_ratios[layer]).quot
                coarse_end[1] = div(end_positions[i,1], grid_ratios[layer]).quot
                cur_ratio = grid_ratios[layer]
                did_hit = c_find_first_pixel(dataptrs[layer],
                                         widths[layer],
                                         heights[layer],
                                         coarse_pos[0],
                                         coarse_pos[1],
                                         coarse_end[0],
                                         coarse_end[1],
                                         &prev_x,
                                         &prev_y,
                                         &hit_x,
                                         &hit_y,
                                         )
                if did_hit:
                    if layer == num_ratios - 1:
                        # hit on the lowest layer (confirmed land hit)
                        last_water_positions[i, 0] = prev_x
                        last_water_positions[i, 1] = prev_y
                        end_positions[i,0] = hit_x
                        end_positions[i,1] = hit_y
                        status_codes[i] = type_defs.OILSTAT_ONLAND
                        break
                    else:
                        # possible hit, go down a layer and try again
                        layer += 1
                        coarse_pos[0] = div(positions[i,0], grid_ratios[layer]).quot
                        coarse_pos[1] = div(positions[i,1], grid_ratios[layer]).quot
                        coarse_end[0] = div(end_positions[i,0], grid_ratios[layer]).quot
                        coarse_end[1] = div(end_positions[i,1], grid_ratios[layer]).quot
                else:
                    # didn't hit land -- can move the LE
                    positions[i, 0] = end_positions[i, 0]
                    positions[i, 1] = end_positions[i, 1]
                    break

        PyMem_Free(coarse_pos)
        PyMem_Free(coarse_end)
        PyMem_Free(dataptrs)
        PyMem_Free(widths)
        PyMem_Free(heights)


def move_particles(cnp.ndarray[cnp.float64_t, ndim=2, mode='c'] positions not None,
                 cnp.ndarray[cnp.float64_t, ndim=2, mode='c'] end_positions not None,
                 cnp.ndarray[int16_t, ndim=1, mode='c'] status_codes not None,
                 cnp.ndarray[cnp.float64_t, ndim=2, mode='c'] last_water_positions not None,
                 cnp.ndarray[cnp.float64_t, ndim=2, mode='c'] land_points not None):

    """
    This land checking algorithm is for use with the parameterized map, a long, straight shoreline.
    """
    cdef cnp.ndarray[cnp.float64_t, ndim=2, mode='c'] shoreline
    shoreline = land_points[0:2]
    cdef cnp.float64_t x1,y1,x2,y2, x3, y3, x4, y4, a1, a2, b1, b2, x, y, u
    [x1, y1], [x2, y2] = shoreline[0], shoreline[1]
    [a1,a2] = shoreline[1] - shoreline[0]

    beaching = points_in_poly(land_points, end_positions)

    for i in range(positions.shape[0]):
        #skip if already landed
        if (status_codes[i] == type_defs.OILSTAT_ONLAND):
            continue
        if (beaching[i]):
            p1, p2 = positions[i][0:2], end_positions[i][0:2]
            [b1,b2] = p2 - p1
            [x3, y3], [x4, y4] = p1, p2
            den = a1 * b2 - b1 * a2
            if (den == 0):
                print a1
                print a2
                print b1
                print b2
                raise ValueError("den is 0")
            u = ((x4-x3)*(y1-y3) - (y4-y3)*(x1-x3))/den
            x = x1 + u * (x2-x1)
            y = y1 + u * (y2-y1)
            end_positions[i,0] = x
            end_positions[i,1] = y
            last_water_positions[i,0] = p1[0] + ( x - p1[0])*0.1
            last_water_positions[i,1] = p1[1] + ( y - p1[1])*0.1
            status_codes[i] = type_defs.OILSTAT_ONLAND
        else:
            positions[i, 0] = end_positions[i, 0]
            positions[i, 1] = end_positions[i, 1]

