"""Personalized monsoon preparedness plan endpoint."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.middleware.sanitize import looks_like_injection, sanitize_free_text
from app.models.schemas import GeneratedTextResponse, PreparednessPlanRequest
from app.prompts.templates import build_preparedness_plan_prompt
from app.services.claude_service import ClaudeServiceError, generate_text
from app.services.weather_service import WeatherServiceError, get_current_weather

logger = logging.getLogger("monsoon_app.preparedness")
router = APIRouter(prefix="/api/preparedness-plan", tags=["preparedness"])


@router.post("", response_model=GeneratedTextResponse)
async def create_preparedness_plan(req: PreparednessPlanRequest) -> GeneratedTextResponse:
    """Generate a personalized, weather-grounded monsoon preparedness plan."""
    req.household.additional_notes = sanitize_free_text(req.household.additional_notes)
    if looks_like_injection(req.household.additional_notes):
        logger.warning("Possible prompt injection attempt in additional_notes, field cleared.")
        req.household.additional_notes = None

    weather = None
    try:
        weather = await get_current_weather(req.location)
    except WeatherServiceError as exc:
        logger.info("Proceeding without live weather grounding: %s", exc)

    system, user = build_preparedness_plan_prompt(req, weather)
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
