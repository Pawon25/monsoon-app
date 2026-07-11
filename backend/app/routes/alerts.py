"""
Real-time severe weather alerts endpoint.

Meant to be polled by the frontend (default every 15 min, configurable via
`alert_poll_interval_seconds`). Combines:
1. Live severe-weather alert data from the weather provider (before/during
   event signals), and
2. Current-conditions heuristics (heavy rain, storms) as a fallback signal
   when the provider has no formal alert but conditions are clearly severe
   (covers the "during/after" phases even if no formal bulletin exists yet).

Claude is only invoked when there is something to localize/phase-tag —
this keeps the endpoint cheap to poll frequently.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import AlertItem, AlertsResponse, Location
from app.prompts.templates import build_alert_localization_prompt
from app.services.claude_service import ClaudeServiceError, generate_json
from app.services.weather_service import (
    WeatherServiceError,
    get_current_weather,
    get_severe_alerts,
)

logger = logging.getLogger("monsoon_app.alerts")
router = APIRouter(prefix="/api/alerts", tags=["alerts"])

_SEVERE_CONDITIONS = {"Thunderstorm", "Tornado", "Squall", "Extreme"}
_HEAVY_RAIN_MM_PER_HOUR = 7.0  # IMD threshold for "heavy rain"


@router.get("", response_model=AlertsResponse)
async def check_alerts(
    city: str | None = Query(default=None, max_length=100),
    state: str | None = Query(default=None, max_length=100),
    country: str = Query(default="IN", max_length=2),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    output_language: str = Query(default="English", max_length=40),
) -> AlertsResponse:
    """Check for active severe weather and return localized, phase-tagged alerts."""
    if not city and (lat is None or lon is None):
        raise HTTPException(status_code=422, detail="Provide either 'city' or both 'lat' and 'lon'.")

    location = Location(city=city, state=state, country=country, lat=lat, lon=lon)

    try:
        weather = await get_current_weather(location)
    except WeatherServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        raw_alerts = await get_severe_alerts(location)
    except WeatherServiceError:
        raw_alerts = []

    heuristic_severe = (weather.condition in _SEVERE_CONDITIONS) or (
        (weather.rain_mm_last_hour or 0) >= _HEAVY_RAIN_MM_PER_HOUR
    )

    if not raw_alerts and not heuristic_severe:
        return AlertsResponse(
            location_resolved=weather.location_resolved,
            has_active_alerts=False,
            alerts=[],
            weather_context=weather,
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    # Synthesize a heuristic alert entry if the provider gave no formal
    # bulletin but current conditions are clearly severe.
    effective_raw_alerts = list(raw_alerts)
    if heuristic_severe and not raw_alerts:
        effective_raw_alerts.append(
            {
                "event": weather.condition or "Heavy rain",
                "description": (
                    f"Current conditions at {weather.location_resolved}: "
                    f"{weather.condition_description or weather.condition}, "
                    f"rainfall {weather.rain_mm_last_hour or 0}mm in the last hour."
                ),
            }
        )

    system, user = build_alert_localization_prompt(
        effective_raw_alerts, weather, location, output_language
    )
    try:
        raw_items = await generate_json(system, user)
        alerts = [AlertItem(**item) for item in raw_items]
    except (ClaudeServiceError, TypeError, ValueError) as exc:
        logger.error("Falling back to raw alert passthrough due to: %s", exc)
        # Graceful degradation: surface the raw provider text rather than failing outright.
        alerts = [
            AlertItem(
                severity="moderate",
                phase="during",
                headline=a.get("event", "Weather Alert"),
                message=(a.get("description") or "Severe weather reported in your area.")[:300],
                source="weather-api-raw",
            )
            for a in effective_raw_alerts
        ]

    return AlertsResponse(
        location_resolved=weather.location_resolved,
        has_active_alerts=True,
        alerts=alerts,
        weather_context=weather,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
