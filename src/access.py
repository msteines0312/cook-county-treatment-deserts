"""
Two-step floating catchment area (2SFCA) access scores.

2SFCA measures how much treatment supply a tract can reach, adjusted for how
many other people are competing for that same supply.

  Step 1: for every site, draw a catchment (a circle of CATCHMENT_MILES) and
          add up the demand from every tract center inside it. The site's
          ratio is its supply divided by that demand.
  Step 2: for every tract, add up the ratios of all sites whose catchment
          reaches it. That sum is the tract's access score.

A clinic that 40 high-need tracts depend on counts for less per tract than
a clinic that only serves 5, which plain "distance to nearest clinic" misses.

Reference: Luo and Wang (2003), "Measures of spatial accessibility to health
care in a GIS environment", Environment and Planning B.
"""

import numpy as np

from src.config import FEET_PER_MILE


def distance_matrix_feet(tract_centers, sites):
    """
    Straight-line distance from every tract center to every site.

    Parameters
    ----------
    tract_centers, sites : gpd.GeoDataFrame
        Point layers in the same projected CRS (EPSG:3435, units of feet).

    Returns
    -------
    np.ndarray
        Shape (number of tracts, number of sites).
    """
    tract_xy = np.column_stack([tract_centers.geometry.x, tract_centers.geometry.y])
    site_xy = np.column_stack([sites.geometry.x, sites.geometry.y])
    # Broadcasting (tracts, 1, 2) against (1, sites, 2) gives every pair at once.
    # 1,331 tracts x ~200 sites is small enough to hold in memory easily.
    differences = tract_xy[:, np.newaxis, :] - site_xy[np.newaxis, :, :]
    return np.sqrt((differences ** 2).sum(axis=2))


def two_step_fca(distances, demand, catchment_miles, min_site_demand=0.0):
    """
    Compute a 2SFCA access score for every tract.

    Parameters
    ----------
    distances : np.ndarray
        Tract-to-site distances in feet, shape (tracts, sites).
    demand : array-like
        Demand at each tract (population, or annual overdose deaths).
    catchment_miles : float
        Radius of each site's catchment.
    min_site_demand : float
        Floor on each site's total demand. Needed for death-based demand: a
        site with zero nearby deaths would otherwise get an infinite ratio.

    Returns
    -------
    np.ndarray
        Access score per tract, in sites per unit of demand. Tracts with no
        site in reach get 0.
    """
    demand = np.asarray(demand, dtype=float)
    # True where the tract is inside the site's catchment
    in_catchment = distances <= catchment_miles * FEET_PER_MILE

    # Step 1: each site's supply (1 site) divided by the demand it serves
    demand_per_site = in_catchment.T @ demand
    demand_per_site = np.maximum(demand_per_site, min_site_demand)
    with np.errstate(divide="ignore"):
        site_ratio = np.where(demand_per_site > 0, 1 / demand_per_site, 0.0)

    # Step 2: each tract sums the ratios of every site that reaches it
    return in_catchment @ site_ratio
