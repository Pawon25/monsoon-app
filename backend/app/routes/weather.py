"""Standalone weather lookup endpoint — used by the frontend to show
current conditions and to ground every other feature's advice."""
from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import Location, WeatherSnapshot
from app.services.weather_service import WeatherServiceError, get_current_weather

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("", response_model=WeatherSnapshot)
async def current_weather(
    city: str | None = Query(default=None, max_length=100),
    state: str | None = Query(default=None, max_length=100),
    country: str = Query(default="IN", max_length=2),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
) -> WeatherSnapshot:
    """Return normalized current weather for a location (city/state or lat/lon)."""
    if not city and (lat is None or lon is None):
        raise HTTPException(status_code=422, detail="Provide either 'city' or both 'lat' and 'lon'.")

    location = Location(city=city, state=state, country=country, lat=lat, lon=lon)
    try:
        return await get_current_weather(location)
    except WeatherServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
