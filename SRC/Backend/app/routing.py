from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
import os
from typing import Protocol

import httpx


@dataclass(frozen=True)
class RouteResult:
    coordinates: list[list[float]]
    distance_km: float
    duration_minutes: float | None
    provider: str
    approximate: bool
    warning: str | None = None


class DirectionsProvider(Protocol):
    async def route(self, origin: tuple[float, float], destination: tuple[float, float]) -> RouteResult: ...


class StraightLineDirectionsProvider:
    async def route(self, origin: tuple[float, float], destination: tuple[float, float]) -> RouteResult:
        earth_radius = 6_371_000
        lat1, lat2 = radians(origin[0]), radians(destination[0])
        d_lat, d_lon = radians(destination[0] - origin[0]), radians(destination[1] - origin[1])
        value = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
        distance = earth_radius * 2 * atan2(sqrt(value), sqrt(1 - value))
        return RouteResult(coordinates=[[origin[0], origin[1]], [destination[0], destination[1]]], distance_km=round(distance / 1000, 1), duration_minutes=None, provider="straight_line", approximate=True)


class OpenRouteServiceDirectionsProvider:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def route(self, origin: tuple[float, float], destination: tuple[float, float]) -> RouteResult:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
                headers={"Authorization": self.api_key, "Content-Type": "application/json"},
                json={"coordinates": [[origin[1], origin[0]], [destination[1], destination[0]]]},
            )
            response.raise_for_status()
            feature = response.json()["features"][0]
            summary = feature["properties"]["summary"]
            coordinates = [[latitude, longitude] for longitude, latitude in feature["geometry"]["coordinates"]]
            return RouteResult(coordinates=coordinates, distance_km=round(summary["distance"] / 1000, 1), duration_minutes=round(summary["duration"] / 60, 1), provider="openrouteservice", approximate=False)


def directions_provider(selected: str | None = None) -> DirectionsProvider:
    selected = selected or os.getenv("DIRECTIONS_PROVIDER", "straight_line")
    if selected == "openrouteservice" and os.getenv("OPENROUTESERVICE_API_KEY"):
        return OpenRouteServiceDirectionsProvider(os.environ["OPENROUTESERVICE_API_KEY"])
    return StraightLineDirectionsProvider()
