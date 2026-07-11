"""Situational safety recommendation endpoint (distinct from the general prep plan)."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.middleware.sanitize import looks_like_injection, sanitize_free_text
from app.models.schemas import GeneratedTextResponse, SafetyRecommendationRequest
from app.prompts.templates import build_safety_recommendation_prompt
from app.services.claude_service import ClaudeServiceError, generate_text
from app.services.weather_service import WeatherServiceError, get_current_weather

logger = logging.getLogger("monsoon_app.safety")
router = APIRouter(prefix="/api/safety-recommendation", tags=["safety"])


@router.post("", response_model=GeneratedTextResponse)
async def create_safety_recommendation(req: SafetyRecommendationRequest) -> GeneratedTextResponse:
    """Generate immediate, situational safety guidance."""
    req.situation = sanitize_free_text(req.situation)
    if looks_like_injection(req.situation):
        logger.warning("Possible prompt injection attempt in situation field, field cleared.")
        req.situation = None

    weather = None
    try:
        weather = await get_current_weather(req.location)
    except WeatherServiceError as exc:
        logger.info("Proceeding without live weather grounding: %s", exc)

    system, user = build_safety_recommendation_prompt(req, weather)
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
