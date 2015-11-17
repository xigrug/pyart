"""
pyart.util.transforms
=====================

Transformations between coordinate systems. Routines for converting between
Cartesian (x, y, z), cartographic (latitude, longitude, altitude) and antenna
(azimuth, elevation, range) coordinate systems.

.. autosummary::
    :toctree: generated/

    antenna_to_cartesian
    sweep_to_cartesian
    antenna_to_cartesian_track_relative
    antenna_to_cartesian_earth_relative
    antenna_to_cartesian_aircraft_relative
    _interpolate_axes_edges
    _interpolate_azimuth_edges
    _interpolate_elevation_edges
    _interpolate_range_edges


"""

import numpy as np


def antenna_to_cartesian(rng, az, ele, debug=False):
    """
    Return cartesian coordinates from antenna coordinates.

    Parameters
    ----------
    rng : array
        Distances to the center of the radar gates (bins) in kilometers.
    az : array
        Azimuth angle of the radar in degrees.
    ele : array
        Elevation angle of the radar in degrees.

    Returns
    -------
    x, y, z : array
        Cartesian coordinates in meters from the radar.

    Notes
    -----
    The calculation for Cartesian coordinate is adapted from equations
    2.28(b) and 2.28(c) of Doviak and Zrnic [1]_ assuming a
    standard atmosphere (4/3 Earth's radius model).

    .. math::

        z = \\sqrt{r^2+R^2+r*R*sin(\\theta_e)} - R

        s = R * arcsin(\\frac{r*cos(\\theta_e)}{R+z})

        x = s * sin(\\theta_a)

        y = s * cos(\\theta_a)

    Where r is the distance from the radar to the center of the gate,
    :math:`\\theta_a` is the azimuth angle, :math:`\\theta_e` is the
    elevation angle, s is the arc length, and R is the effective radius
    of the earth, taken to be 4/3 the mean radius of earth (6371 km).

    References
    ----------
    .. [1] Doviak and Zrnic, Doppler Radar and Weather Observations, Second
        Edition, 1993, p. 21.

    """
    theta_e = ele * np.pi / 180.0       # elevation angle in radians.
    theta_a = az * np.pi / 180.0        # azimuth angle in radians.
    R = 6371.0 * 1000.0 * 4.0 / 3.0     # effective radius of earth in meters.
    r = rng * 1000.0                    # distances to gates in meters.

    z = (r ** 2 + R ** 2 + 2.0 * r * R * np.sin(theta_e)) ** 0.5 - R
    s = R * np.arcsin(r * np.cos(theta_e) / (R + z))  # arc length in m.
    x = s * np.sin(theta_a)
    y = s * np.cos(theta_a)
    return x, y, z


def sweep_to_cartesian(ranges, azimuths, elevations, edges=False):
    """
    Calculate Cartesian coordinate for the gates in a single radar sweep.

    Calculates the Cartesian coordinates for the gate centers or edges for
    all gates in a single sweep assuming a standard atmosphere (4/3 Earth's
    radius model). See :py:func:`pyart.util.antenna_to_cartesian` for
    details.

    Parameters
    ----------
    ranges : array, 1D.
        Distances to the center of the radar gates (bins) in meters.
    azimuths : array, 1D.
        Azimuth angles of the sweep in degrees.
    elevations : array, 1D.
        Elevation angles of the sweep in degrees.
    edges : bool, optional
        True to calculate the coordinates of the gate edges by interpolating
        between gates and extrapolating at the boundaries.  False to
        calculate the gate centers.

    Returns
    -------
    x, y, z : array, 2D
        Cartesian coordinates in meters from the center of the radar to the
        gate centers or edges.

    """
    if edges:
        if len(ranges) != 1:
            ranges = _interpolate_range_edges(ranges)
        if len(elevations) != 1:
            elevations = _interpolate_elevation_edges(elevations)
        if len(azimuths) != 1:
            azimuths = _interpolate_azimuth_edges(azimuths)
    rg, azg = np.meshgrid(ranges, azimuths)
    rg, eleg = np.meshgrid(ranges, elevations)
    return antenna_to_cartesian(rg / 1000., azg, eleg)


def _interpolate_range_edges(ranges):
    """ Interpolate the edges of the range gates from their centers. """
    edges = np.empty((ranges.shape[0] + 1, ), dtype=ranges.dtype)
    edges[1:-1] = (ranges[:-1] + ranges[1:]) / 2.
    edges[0] = ranges[0] - (ranges[1] - ranges[0]) / 2.
    edges[-1] = ranges[-1] - (ranges[-2] - ranges[-1]) / 2.
    edges[edges < 0] = 0    # do not allow range to become negative
    return edges


def _interpolate_elevation_edges(elevations):
    """ Interpolate the edges of the elevation angles from their centers. """
    edges = np.empty((elevations.shape[0]+1, ), dtype=elevations.dtype)
    edges[1:-1] = (elevations[:-1] + elevations[1:]) / 2.
    edges[0] = elevations[0] - (elevations[1] - elevations[0]) / 2.
    edges[-1] = elevations[-1] - (elevations[-2] - elevations[-1]) / 2.
    edges[edges > 180] = 180.   # prevent angles from going below horizon
    edges[edges < 0] = 0.
    return edges


def _interpolate_azimuth_edges(azimuths):
    """ Interpolate the edges of the azimuth angles from their centers. """
    edges = np.empty((azimuths.shape[0]+1, ), dtype=azimuths.dtype)
    # perform interpolation and extrapolation in complex plane to
    # account for periodic nature of azimuth angle.
    az = np.exp(1.j*np.deg2rad(azimuths))
    edges[1:-1] = np.angle((az[1:] + az[:-1]) / 2., deg=True)
    edges[0] = np.angle(az[0] - (az[1] - az[0]) / 2., deg=True)
    edges[-1] = np.angle(az[-1] - (az[-2] - az[-1]) / 2., deg=True)
    edges[edges < 0] += 360     # range from [-180, 180] to [0, 360]
    return edges


def _interpolate_axes_edges(axes):
    """ Interpolate the edges of the axes gates from their centers. """
    edges = np.empty((axes.shape[0] + 1, ), dtype=axes.dtype)
    edges[1:-1] = (axes[:-1] + axes[1:]) / 2.
    edges[0] = axes[0] - (axes[1] - axes[0]) / 2.
    edges[-1] = axes[-1] - (axes[-2] - axes[-1]) / 2.
    return edges


def antenna_to_cartesian_track_relative(rng, rot, roll, drift, tilt, pitch):
    """
    Calculate track-relative Cartesian coordinates from radar coordinates.

    Parameters
    ----------
    rng : array
        Distances to the center of the radar gates (bins) in kilometers.
    rot : array
        Rotation angle of the radar in degrees.
    roll : array
        Roll angle of the radar in degrees.
    drift : array
        Drift angle of the radar in degrees.
    tilt : array
        Tilt angle of the radar in degrees.
    pitch : array
        Pitch angle of the radar in degrees.

    Returns
    -------
    x, y, z : array
        Cartesian coordinates in meters from the radar.

    Notes
    -----
    Project native (polar) coordinate radar sweep data onto
    track-relative Cartesian coordinate grid.

    References
    ----------
    .. [1] Lee et al. (1994) Journal of Atmospheric and Oceanic Technology.

    """
    rot = np.radians(rot)               # rotation angle in radians.
    roll = np.radians(roll)             # roll angle in radians.
    drift = np.radians(drift)           # drift angle in radians.
    tilt = np.radians(tilt)             # tilt angle in radians.
    pitch = np.radians(pitch)           # pitch angle in radians.
    r = rng * 1000.0                    # distances to gates in meters.

    x = r * (np.cos(rot + roll) * np.sin(drift) * np.cos(tilt) *
             np.sin(pitch) + np.cos(drift) * np.sin(rot + roll) *
             np.cos(tilt) - np.sin(drift) * np.cos(pitch) * np.sin(tilt))
    y = r * (-1. * np.cos(rot + roll) * np.cos(drift) * np.cos(tilt) *
             np.sin(pitch) + np.sin(drift) * np.sin(rot + roll) *
             np.cos(tilt) + np.cos(drift) * np.cos(pitch) * np.sin(tilt))
    z = (r * np.cos(pitch) * np.cos(tilt) * np.cos(rot + roll) +
         np.sin(pitch) * np.sin(tilt))
    return x, y, z


def antenna_to_cartesian_earth_relative(rng, rot, roll, heading, tilt, pitch):
    """
    Calculate earth-relative Cartesian coordinates from radar coordinates

    Parameters
    ----------
    rng : array
        Distances to the center of the radar gates (bins) in kilometers.
    rot : array
        Rotation angle of the radar in degrees.
    roll : array
        Roll angle of the radar in degrees.
    heading : array
        Heading (compass) angle of the radar in degrees clockwise from north.
    tilt : array
        Tilt angle of the radar in degrees.
    pitch : array
        Pitch angle of the radar in degrees.

    Returns
    -------
    x, y, z : array
        Cartesian coordinates in meters from the radar.

    Notes
    -----
    Project native (polar) coordinate radar sweep data onto
    earth-relative Cartesian coordinate grid.

    References
    ----------
    .. [1] Lee et al. (1994) Journal of Atmospheric and Oceanic Technology.

    """
    rot = np.radians(rot)               # rotation angle in radians.
    roll = np.radians(roll)             # roll angle in radians.
    heading = np.radians(heading)       # drift angle in radians.
    tilt = np.radians(tilt)             # tilt angle in radians.
    pitch = np.radians(pitch)           # pitch angle in radians.
    r = rng * 1000.0                    # distances to gates in meters.

    x = r * (-1. * np.cos(rot + roll) * np.sin(heading) * np.cos(tilt) *
             np.sin(pitch) + np.cos(heading) * np.sin(rot + roll) *
             np.cos(tilt) + np.sin(heading) * np.cos(pitch) * np.sin(tilt))
    y = r * (-1. * np.cos(rot + roll) * np.cos(heading) * np.cos(tilt) *
             np.sin(pitch) - np.sin(heading) * np.sin(rot + roll) *
             np.cos(tilt) + np.cos(heading) * np.cos(pitch) * np.sin(tilt))
    z = (r * np.cos(pitch) * np.cos(tilt) * np.cos(rot + roll) +
         np.sin(pitch) * np.sin(tilt))
    return x, y, z


def antenna_to_cartesian_aircraft_relative(rng, rot, tilt):
    """
    Calculate aircraft-relative Cartesian coordinates from radar coordinates.

    Parameters
    ----------
    rng : array
        Distances to the center of the radar gates (bins) in kilometers.
    rot : array
        Rotation angle of the radar in degrees.
    tilt : array
        Tilt angle of the radar in degrees.

    Returns
    -------
    X, Y, Z : array
        Cartesian coordinates in meters from the radar.

    Notes
    -----
    Project native (polar) coordinate radar sweep data onto
    earth-relative Cartesian coordinate grid.

    References
    ----------
    .. [1] Lee et al. (1994) Journal of Atmospheric and Oceanic Technology.

    """
    rot = np.radians(rot)               # rotation angle in radians.
    tilt = np.radians(tilt)             # tilt angle in radians.
    r = rng * 1000.0                    # distances to gates in meters.
    x = r * np.cos(tilt) * np.sin(rot)
    y = r * np.sin(tilt)
    z = r * np.cos(rot) * np.cos(tilt)
    return x, y, z
