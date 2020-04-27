# -*- coding: utf-8 -*-
"""
Created on Sun Apr 26 15:01:57 2020

Speed of sound calculation package

@author: Rainer
"""

#pylint: disable=C0103

import numpy as np

watertriplepointtemp = 273.16 # in Kelvin
watercriticalpointtemp = 647.096 # in Kelvin
watertriplepointpress = 611.657 # in Pa
watercriticalpointpress = 22064000 # in Pa
molmasswater = 18.01528 # in g/mol
molmassair = 28.9647 # in g/mol
molmassratio = molmasswater / molmassair # unitless
molargasconstant = 8314.4598 # in kg m² / (s² K kmol)
molweightratio = molmasswater/molmassair
specific_heat_constant_pressure_air = 1005 # in Joule / (kg K)
specific_heat_constant_pressure_vapour_const = 1820 # in Joule / (kg K ), approximation

psatpars = np.array([[611.21, 18.678, 234.5, 257.14], [611.15, 23.036, 333.7, 279.82]])

def saturated_vapour_pressure(temp):
    """
    Parameters
    ----------
    temp : float
        Temperature of humid air [°C]

    Returns
    -------
    float
        saturation partial pressure of water vapour [Pa]

    """

    return np.where(temp >= 0,
                    psatpars[0, 0] * np.exp((psatpars[0, 1] - temp / psatpars[0, 2]) * \
                                            (temp / (psatpars[0, 3] + temp))),
                    psatpars[1, 0] * np.exp((psatpars[1, 1] - temp / psatpars[1, 2]) * \
                                            (temp / (psatpars[1, 3] + temp)))
                    )

def saturated_vapour_temperature(pressure, above_ice=False):
    """

    Parameters
    ----------
    pressure : float
        partial pressure of water vapour [Pa]

    above_ice: Boolean
        if above_ice is true the (negative) temperature when saturation is reached is returned

    Returns
    -------
    float
        temperature of saturated water vapour at given pressure. [°C]

    """

    i = 1 if above_ice else 0
    t1logA = psatpars[i, 2] * np.log(psatpars[i, 0] / pressure)
    Et1 = psatpars[i, 1] * psatpars[i, 2]
    return (Et1 + t1logA - np.sqrt(4 * psatpars[i, 3] * t1logA + np.power(-Et1 - t1logA, 2))) / 2

def mass_mixing_ratio(spechum):
    """


    Parameters
    ----------
    specific_humidity : float
        specific humidity in kg/kg

    Returns
    -------
    float
        mass mixing ratio

    """
    return spechum / (1 - spechum)

def specific_humidity(temp, pressure, relhumidity):
    """


    Parameters
    ----------
    temp : float
        Temperature of humid air [°C]
    pressure : TYPE
        Humid air pressure [Pa]
    relhumidity : TYPE
        relative humidity [%]

    Returns
    -------
    float
        specific humidity in kg/kg

    """

    pvapsat = saturated_vapour_pressure(temp)
    return relhumidity * molweightratio * pvapsat / (pressure - pvapsat)

def specific_heat_constant_pressure_vapour(pvapour, temp):
    """


    Parameters
    ----------
    pvapour : float
        partial pressure of water vapour (depending on relative humidity) [Pa]
    temp : float
        Temperature of humid air [°C].

    Returns
    -------
    float
        specific heat of water vapour at given partial pressure and temperature

    """
    ABC_E = np.array([[1877.2, -0.49545, 0.0081818], [1856.1, 0.28056, 0.00069444]])
    ABC_F = np.array([22.537, 0.49321, 0.048927])

    return np.where(temp < 50,
                    ABC_E[0, 0] + temp * (ABC_E[0, 1] + temp * ABC_E[0, 2]) + \
                    (pvapour - watertriplepointpress) / \
                    (ABC_F[0] + temp * (ABC_F[1] + temp * ABC_F[2]))
                    ,
                    ABC_E[1, 0] + temp * (ABC_E[1, 1] + temp * ABC_E[1, 2]) + \
                    (pvapour - watertriplepointpress) / \
                    (ABC_F[0] + temp * (ABC_F[1] + temp * ABC_F[2]))
                    )

def speed_of_sound(temp, pressure, relhumididy, approx=False):
    """

    Parameters
    ----------
    temp : float
        Temperature of humid air [°C]
    pressure : float
        Humid air pressure [Pa]
    relhumididy : float
        relative humidity [%]
    approx : int
        if approx == 0 or False we use the full accuracy taking into account
        the dependency on humidity, the dependency of cp on temperature and
        the dependency of the partial pressure on temperature
        if approx == 1 we assume that cp is constant
        if approx == 2 we neglect the effect of humidity
        if approx == 3 we use a taylor expansion of the speed equation for dry air

    Returns
    -------
    float
        Speed of sound in air in m/s

    """

    # Absolute Humidity from temperature pressure and relative humidity
    if approx >= 2:
        pvapour = 0
        H = 0
        zeta = 0
    else:
        pvapour = relhumididy * saturated_vapour_pressure(temp)
        H = specific_humidity(temp, pressure, relhumididy) # in kg/kg
        zeta = mass_mixing_ratio(H)
    # molar mass of humid air
    Mhum = (molmassratio * molmassair + zeta * molmasswater) / (molmassratio + zeta)
    # Specific gas constant of humid air
    R = molargasconstant / Mhum # in m² / (s² K)
    # Specific heat of moist air at constant pressure
    if approx == 1:
        cp = specific_heat_constant_pressure_air + \
            H * specific_heat_constant_pressure_vapour_const # in J / (kg K)
    else:
        cp = specific_heat_constant_pressure_air + \
            H * specific_heat_constant_pressure_vapour(pvapour, temp)
    # Specific heat of moist air at constant volume
    cv = cp - R
    # Adiabatic index
    gamma = cp / cv

    if approx == 3:
        return np.sqrt(gamma * R * 273.15) * (1 + 1/(2*273.15) * temp) # in m/s
    return np.sqrt(gamma * R * (temp + 273.15)) # in m/s
