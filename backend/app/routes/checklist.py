"""Emergency checklist generation endpoint."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.middleware.sanitize import looks_like_injection, sanitize_free_text
from app.models.schemas import ChecklistItem, ChecklistRequest, ChecklistResponse
from app.prompts.templates import build_checklist_prompt
from app.services.claude_service import ClaudeServiceError, generate_json
from app.services.weather_service import WeatherServiceError, get_current_weather

logger = logging.getLogger("monsoon_app.checklist")
router = APIRouter(prefix="/api/checklist", tags=["checklist"])


@router.post("", response_model=ChecklistResponse)
async def create_checklist(req: ChecklistRequest) -> ChecklistResponse:
    """Generate a household- and weather-aware monsoon emergency checklist."""
    req.household.additional_notes = sanitize_free_text(req.household.additional_notes)
    if looks_like_injection(req.household.additional_notes):
        logger.warning("Possible prompt injection attempt in additional_notes, field cleared.")
        req.household.additional_notes = None

    weather = None
    try:
        weather = await get_current_weather(req.location)
    except WeatherServiceError as exc:
        logger.info("Proceeding without live weather grounding: %s", exc)

    system, user = build_checklist_prompt(req, weather)
    try:
        raw_items = await generate_json(system, user)
    except ClaudeServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        items = [ChecklistItem(**item) for item in raw_items]
    except (TypeError, ValueError) as exc:
        logger.error("Checklist JSON did not match expected shape: %s", exc)
        raise HTTPException(status_code=503, detail="The AI service returned an unexpected checklist format.") from exc

    return ChecklistResponse(
        items=items,
        language=req.output_language,
        weather_context=weather,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
