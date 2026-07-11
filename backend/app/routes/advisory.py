"""Monsoon travel advisory endpoint."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.models.schemas import GeneratedTextResponse, TravelAdvisoryRequest
from app.prompts.templates import build_travel_advisory_prompt
from app.services.claude_service import ClaudeServiceError, generate_text
from app.services.weather_service import WeatherServiceError, get_current_weather

logger = logging.getLogger("monsoon_app.advisory")
router = APIRouter(prefix="/api/travel-advisory", tags=["advisory"])


@router.post("", response_model=GeneratedTextResponse)
async def create_travel_advisory(req: TravelAdvisoryRequest) -> GeneratedTextResponse:
    """Generate a travel advisory grounded in destination weather conditions."""
    weather = None
    try:
        weather = await get_current_weather(req.destination)
    except WeatherServiceError as exc:
        logger.info("Proceeding without live weather grounding: %s", exc)

    system, user = build_travel_advisory_prompt(req, weather)
    try:
        content = await generate_text(system, user)
    except ClaudeServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return GeneratedTextResponse(
        content=content,
        language=req.output_language,
        weather_context=weather,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
