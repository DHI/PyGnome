
class Stokes(object):
    @staticmethod
    def water_phase_xfer_velocity(oil_water_rho_delta, diameter):
        '''
            water phase transfer velocity k_w (m/s)

            This assumes spherical droplets with a diameter < 400 microns.

            Bigger droplets will be distorted and rise more rapidly, and
            they are presumed to rise so quickly that little dissolution
            takes place for them except as part of the dissolution from
            the surface slick.

            :param oil_water_rho_delta: density difference (unit-less)
            :param diameter: droplet diameter (m)

            :returns: transfer velocity (m/s)
        '''
        return 544.814 * oil_water_rho_delta * diameter ** 2
