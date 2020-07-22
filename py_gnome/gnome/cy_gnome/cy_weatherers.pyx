cimport numpy as cnp
import numpy as np

# following exist in gnome.cy_gnome
from type_defs cimport *
from utils cimport emulsify
from utils cimport adios2_disperse
from libc.stdint cimport *


def emulsify_oil(step_len, cnp.ndarray[cnp.npy_double] frac_water,
                 cnp.ndarray[cnp.npy_double] le_interfacial_area,
                 cnp.ndarray[cnp.npy_double] le_frac_evap,
                 cnp.ndarray[int32_t] le_age,
                 cnp.ndarray[cnp.npy_double] le_bulltime,
                 cnp.ndarray[cnp.npy_double] k_emul,
                 double emul_time,
                 double emul_C,
                 double S_max,
                 double Y_max,
                 double drop_max):
    """
    """
    cdef OSErr emul_err
    # N = len(frac_water)
    N = len(le_age)

    emul_err = emulsify(N,
                        step_len,
                        & frac_water[0],
                        & le_interfacial_area[0],
                        & le_frac_evap[0],
                        & le_age[0],
                        & le_bulltime[0],
                        & k_emul[0],
                        emul_time,
                        emul_C,
                        S_max,
                        Y_max,
                        drop_max)

    if emul_err != 0:
        raise ValueError("C++ call to emulsify returned error code: "
                         "{0}".format(emul_err))


def disperse_oil(step_len, cnp.ndarray[cnp.npy_double] frac_water,
                 cnp.ndarray[cnp.npy_double] le_mass,
                 cnp.ndarray[cnp.npy_double] le_viscosity,
                 cnp.ndarray[cnp.npy_double] le_density,
                 cnp.ndarray[cnp.npy_double] fay_area,
                 cnp.ndarray[cnp.npy_double] d_disp,
                 cnp.ndarray[cnp.npy_double] d_sed,
                 cnp.ndarray[cnp.npy_double] droplet_avg_size,
                 cnp.ndarray[cnp.npy_double] frac_breaking_waves,
                 cnp.ndarray[cnp.npy_double] disp_wave_energy,
                 cnp.ndarray[cnp.npy_double] wave_height,
                 double visc_w,
                 double rho_w,
                 double C_sed,
                 double V_entrain,
                 double ka):
    """
    """
    cdef OSErr disp_err
    # N = len(frac_water)
    N = len(le_mass)

    disp_err = adios2_disperse(N,
                               step_len,
                               & frac_water[0],
                               & le_mass[0],
                               & le_viscosity[0],
                               & le_density[0],
                               & fay_area[0],
                               & d_disp[0],
                               & d_sed[0],
                               & droplet_avg_size[0],
                               & frac_breaking_waves[0],
                               & disp_wave_energy[0],
                               & wave_height[0],
                               visc_w,
                               rho_w,
                               C_sed,
                               V_entrain,
                               ka)

    if disp_err != 0:
        raise ValueError("C++ call to disperse returned error code: "
                         "{0}".format(disp_err))
