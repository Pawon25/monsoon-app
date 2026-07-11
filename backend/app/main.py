"""
Monsoon Preparedness & Citizen Assistance API — entrypoint.

Session-less, no-auth public API. See README.md for endpoint docs and
deployment notes.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.routes import advisory, alerts, checklist, preparedness, safety, weather
from app.services.claude_service import ClaudeServiceError
from app.services.weather_service import WeatherServiceError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("monsoon_app")

settings = get_settings()

app = FastAPI(
    title="Monsoon Preparedness & Citizen Assistance API",
    description="GenAI-powered monsoon preparedness, alerts, and travel/safety guidance.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(RateLimitMiddleware)

app.include_router(preparedness.router)
app.include_router(checklist.router)
app.include_router(advisory.router)
app.include_router(safety.router)
app.include_router(alerts.router)
app.include_router(weather.router)


@app.exception_handler(WeatherServiceError)
async def weather_error_handler(request: Request, exc: WeatherServiceError) -> JSONResponse:
    logger.warning("WeatherServiceError on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=502, content={"error": "weather_service_error", "detail": str(exc)})


@app.exception_handler(ClaudeServiceError)
async def claude_error_handler(request: Request, exc: ClaudeServiceError) -> JSONResponse:
    logger.warning("ClaudeServiceError on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"error": "ai_service_error", "detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": "Something went wrong."})


@app.get("/api/health", tags=["meta"])
async def health_check() -> dict:
    """Basic liveness check + config sanity flags (no secrets exposed)."""
    return {
        "status": "ok",
        "claude_configured": bool(settings.anthropic_api_key),
        "weather_configured": bool(settings.openweather_api_key),
        "suggested_languages": settings.suggested_languages,
        "alert_poll_interval_seconds": settings.alert_poll_interval_seconds,
    }
