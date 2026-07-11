"""
Weather data service — talks to OpenWeatherMap server-side only.

Provides:
- geocode(): resolve a place name to lat/lon
- get_current_weather(): normalized current conditions snapshot
- get_severe_alerts(): active severe-weather alerts for a location

All calls are cached briefly (see services/cache.py) to avoid redundant
upstream requests, and all raise `WeatherServiceError` on failure so
callers (routes) can decide how to degrade gracefully instead of crashing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from app.config import get_settings
from app.models.schemas import Location, WeatherSnapshot
from app.services.cache import weather_cache

logger = logging.getLogger("monsoon_app.weather")


class WeatherServiceError(Exception):
    """Raised when weather data cannot be retrieved."""


async def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=8.0)


async def geocode(location: Location) -> Location:
    """Fill in lat/lon on a Location if not already present, via OWM geocoding."""
    if location.has_coords():
        return location

    settings = get_settings()
    if not settings.openweather_api_key:
        raise WeatherServiceError("Weather API key not configured on server.")

    query = location.query_string()
    cache_key = f"geo:{query.lower()}"
    cached = weather_cache.get(cache_key)
    if cached:
        return cached

    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {"q": query, "limit": 1, "appid": settings.openweather_api_key}

    try:
        async with await _get_client() as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Geocoding failed for %s: %s", query, exc)
        raise WeatherServiceError(f"Could not resolve location '{query}'.") from exc

    if not data:
        raise WeatherServiceError(f"No location found matching '{query}'.")

    resolved = Location(
        city=data[0].get("name", location.city),
        state=location.state,
        country=data[0].get("country", location.country),
        lat=data[0]["lat"],
        lon=data[0]["lon"],
    )
    weather_cache.set(cache_key, resolved, ttl_seconds=3600)
    return resolved


async def get_current_weather(location: Location) -> WeatherSnapshot:
    """Fetch current conditions, using a short-TTL cache keyed by rounded coords."""
    settings = get_settings()
    if not settings.openweather_api_key:
        raise WeatherServiceError("Weather API key not configured on server.")

    resolved = await geocode(location)
    cache_key = f"weather:{round(resolved.lat, 2)},{round(resolved.lon, 2)}"
    cached = weather_cache.get(cache_key)
    if cached:
        return cached

    url = f"{settings.openweather_base_url}/weather"
    params = {
        "lat": resolved.lat,
        "lon": resolved.lon,
        "appid": settings.openweather_api_key,
        "units": "metric",
    }

    try:
        async with await _get_client() as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("Current weather fetch failed: %s", exc)
        raise WeatherServiceError("Could not fetch current weather conditions.") from exc

    snapshot = WeatherSnapshot(
        location_resolved=resolved.query_string(),
        temperature_c=data.get("main", {}).get("temp"),
        feels_like_c=data.get("main", {}).get("feels_like"),
        humidity_pct=data.get("main", {}).get("humidity"),
        wind_speed_ms=data.get("wind", {}).get("speed"),
        rain_mm_last_hour=data.get("rain", {}).get("1h"),
        condition=(data.get("weather") or [{}])[0].get("main"),
        condition_description=(data.get("weather") or [{}])[0].get("description"),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    weather_cache.set(cache_key, snapshot, ttl_seconds=settings.weather_cache_ttl_seconds)
    return snapshot


async def get_severe_alerts(location: Location) -> List[dict]:
    """
    Fetch active severe-weather alerts via OWM One Call API.

    Degrades to an empty list (rather than raising) if the One Call
    endpoint is unavailable, since alerts are supplementary to the core
    weather snapshot and many free-tier keys have limited access.
    """
    settings = get_settings()
    if not settings.openweather_api_key:
        raise WeatherServiceError("Weather API key not configured on server.")

    resolved = await geocode(location)
    cache_key = f"alerts:{round(resolved.lat, 2)},{round(resolved.lon, 2)}"
    cached = weather_cache.get(cache_key)
    if cached is not None:
        return cached

    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": resolved.lat,
        "lon": resolved.lon,
        "appid": settings.openweather_api_key,
        "exclude": "minutely,hourly,daily,current",
        "units": "metric",
    }

    alerts: List[dict] = []
    try:
        async with await _get_client() as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                alerts = resp.json().get("alerts", [])
    except httpx.HTTPError as exc:
        logger.info("Severe alert fetch unavailable, degrading to no-alerts: %s", exc)

    weather_cache.set(cache_key, alerts, ttl_seconds=settings.weather_cache_ttl_seconds)
    return alerts
