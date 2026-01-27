"""Qibla direction calculation utilities."""

from __future__ import annotations

import math

# Kaaba coordinates (Mecca)
KAABA_LATITUDE = 21.4225
KAABA_LONGITUDE = 39.8262


def calculate_qibla_direction(latitude: float, longitude: float) -> float:
    """Calculate the Qibla direction (bearing to Mecca) from a given location.

    Args:
        latitude: Observer's latitude in degrees.
        longitude: Observer's longitude in degrees.

    Returns:
        Qibla direction in degrees from North (0-360).
    """
    # Convert to radians
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)
    lat2 = math.radians(KAABA_LATITUDE)
    lon2 = math.radians(KAABA_LONGITUDE)

    # Calculate the difference in longitude
    delta_lon = lon2 - lon1

    # Calculate bearing using the spherical law of cosines
    x = math.sin(delta_lon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        delta_lon
    )

    # Calculate initial bearing
    bearing = math.atan2(x, y)

    # Convert to degrees
    bearing_degrees = math.degrees(bearing)

    # Normalize to 0-360
    qibla_direction = (bearing_degrees + 360) % 360

    return round(qibla_direction, 2)


def get_qibla_compass_direction(qibla_degrees: float) -> str:
    """Get compass direction name for Qibla.

    Args:
        qibla_degrees: Qibla direction in degrees.

    Returns:
        Compass direction name (N, NE, E, SE, S, SW, W, NW).
    """
    directions = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]

    # Each direction covers 22.5 degrees
    index = round(qibla_degrees / 22.5) % 16
    return directions[index]


def calculate_distance_to_mecca(latitude: float, longitude: float) -> float:
    """Calculate the distance to Mecca in kilometers.

    Uses the Haversine formula for great-circle distance.

    Args:
        latitude: Observer's latitude in degrees.
        longitude: Observer's longitude in degrees.

    Returns:
        Distance to Mecca in kilometers.
    """
    # Earth's radius in kilometers
    earth_radius = 6371.0

    # Convert to radians
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)
    lat2 = math.radians(KAABA_LATITUDE)
    lon2 = math.radians(KAABA_LONGITUDE)

    # Haversine formula
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    distance = earth_radius * c
    return round(distance, 1)
