"""
Route Optimization — Nearest Neighbour Heuristic.

Reference:
  Laporte, G. (1992). The traveling salesman problem: An overview of
  exact and approximate algorithms. European Journal of Operational Research,
  59(2), 231–247.

  Sinnott, R. W. (1984). Virtues of the Haversine. Sky and Telescope, 68(2), 159.
  (Haversine formula for great-circle distance)

Complexity: O(n²) — suitable for up to ~500 distribution points on modest hardware.
"""

import math
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometres between two geographic
    coordinates using the Haversine formula.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


# ---------------------------------------------------------------------------
# Nearest Neighbour Algorithm
# ---------------------------------------------------------------------------

def nearest_neighbour_route(
    origin: Tuple[float, float],
    points: List[Tuple[int, float, float]],
) -> Tuple[List[Tuple[int, float, float, float]], float]:
    """
    Build a delivery route from an origin using the Nearest Neighbour heuristic.

    Parameters
    ----------
    origin  : (latitude, longitude) of the source warehouse.
    points  : List of (id, latitude, longitude) tuples for distribution points.

    Returns
    -------
    ordered_stops : List of (id, lat, lon, dist_from_prev_km) in visit order.
    total_km      : Total route distance in kilometres.

    The route does NOT loop back to the origin (open TSP variant),
    which is the practical case for one-way aid deliveries.
    """
    if not points:
        return [], 0.0

    unvisited = list(points)          # [(id, lat, lon), ...]
    current_lat, current_lon = origin
    ordered_stops: List[Tuple[int, float, float, float]] = []
    total_km = 0.0

    while unvisited:
        # Find the nearest unvisited point from the current position
        best_idx = None
        best_dist = float("inf")

        for i, (pid, plat, plon) in enumerate(unvisited):
            d = haversine(current_lat, current_lon, plat, plon)
            if d < best_dist:
                best_dist = d
                best_idx = i

        # Visit the nearest point
        chosen = unvisited.pop(best_idx)
        pid, plat, plon = chosen
        total_km += best_dist
        ordered_stops.append((pid, plat, plon, round(best_dist, 3)))
        current_lat, current_lon = plat, plon

    return ordered_stops, round(total_km, 3)


# ---------------------------------------------------------------------------
# Convenience wrapper used by the distribution routes blueprint
# ---------------------------------------------------------------------------

def optimise_route_for_points(warehouse, distribution_points):
    """
    High-level helper that accepts ORM objects and returns a structured result.

    Parameters
    ----------
    warehouse           : Warehouse ORM instance (must have .latitude, .longitude)
    distribution_points : List of DistributionPoint ORM instances

    Returns
    -------
    {
        "ordered_stops": [
            {
                "id": int,
                "name": str,
                "latitude": float,
                "longitude": float,
                "distance_from_prev_km": float,
            },
            ...
        ],
        "total_distance_km": float,
    }
    """
    origin = (warehouse.latitude, warehouse.longitude)
    raw_points = [
        (dp.id, dp.latitude, dp.longitude)
        for dp in distribution_points
        if dp.latitude and dp.longitude
    ]

    # Build id → name lookup
    id_to_name = {dp.id: dp.name for dp in distribution_points}

    ordered_raw, total_km = nearest_neighbour_route(origin, raw_points)

    ordered_stops = [
        {
            "id": pid,
            "name": id_to_name.get(pid, "Unknown"),
            "latitude": plat,
            "longitude": plon,
            "distance_from_prev_km": dist,
        }
        for pid, plat, plon, dist in ordered_raw
    ]

    return {
        "ordered_stops": ordered_stops,
        "total_distance_km": total_km,
    }
