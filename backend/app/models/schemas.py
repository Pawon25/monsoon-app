"""
Pydantic models for request validation and response shaping.

Every user-facing endpoint validates through one of these models. Free-text
fields that get interpolated into Claude prompts are length-capped here as
a first line of defense against prompt injection / abuse (see
app/middleware/sanitize.py for the second line).
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class RiskLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    severe = "severe"


class Location(BaseModel):
    """Location can be given as a place name and/or coordinates."""

    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    country: str = Field(default="IN", max_length=2)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)

    @field_validator("city", "state")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    def has_coords(self) -> bool:
        return self.lat is not None and self.lon is not None

    def query_string(self) -> str:
        """Best-effort human readable location string for prompts / geocoding."""
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts) if parts else f"{self.lat},{self.lon}"


class HouseholdDetails(BaseModel):
    household_size: int = Field(default=1, ge=1, le=30)
    has_children: bool = False
    has_elderly: bool = False
    has_pets: bool = False
    has_disabled_members: bool = False
    dwelling_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="e.g. apartment, independent house, low-lying area, slum/informal housing",
    )
    risk_level: RiskLevel = RiskLevel.moderate
    additional_notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("additional_notes", "dwelling_type")
    @classmethod
    def strip_text(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class BaseLocalizedRequest(BaseModel):
    location: Location
    output_language: str = Field(
        default="English",
        max_length=40,
        description="Any language name, e.g. English, Hindi, Kannada, Marathi...",
    )

    @field_validator("output_language")
    @classmethod
    def clean_language(cls, v: str) -> str:
        v = v.strip()
        if not v:
            return "English"
        return v[:40]


class PreparednessPlanRequest(BaseLocalizedRequest):
    household: HouseholdDetails


class ChecklistRequest(BaseLocalizedRequest):
    household: HouseholdDetails


class TravelAdvisoryRequest(BaseLocalizedRequest):
    destination: Location
    travel_date: Optional[str] = Field(default=None, max_length=20)
    mode_of_travel: Optional[str] = Field(
        default=None, max_length=30, description="e.g. car, bus, train, flight, two-wheeler"
    )


class SafetyRecommendationRequest(BaseLocalizedRequest):
    household: HouseholdDetails
    situation: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Free-text current situation, e.g. 'water entering ground floor'",
    )


class AlertsRequest(BaseModel):
    location: Location
    output_language: str = Field(default="English", max_length=40)

    @field_validator("output_language")
    @classmethod
    def clean_language(cls, v: str) -> str:
        v = v.strip()
        return v[:40] if v else "English"


class WeatherSnapshot(BaseModel):
    """Normalized weather data shape used across services and prompts."""

    location_resolved: str
    temperature_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    humidity_pct: Optional[int] = None
    wind_speed_ms: Optional[float] = None
    rain_mm_last_hour: Optional[float] = None
    condition: Optional[str] = None
    condition_description: Optional[str] = None
    alerts: List[dict] = Field(default_factory=list)
    fetched_at: str


class GeneratedTextResponse(BaseModel):
    content: str
    language: str
    weather_context: Optional[WeatherSnapshot] = None
    generated_at: str


class ChecklistItem(BaseModel):
    category: str
    item: str
    priority: str = "normal"


class ChecklistResponse(BaseModel):
    items: List[ChecklistItem]
    language: str
    weather_context: Optional[WeatherSnapshot] = None
    generated_at: str


class AlertItem(BaseModel):
    severity: str
    phase: str  # before | during | after
    headline: str
    message: str
    source: str = "weather-api"


class AlertsResponse(BaseModel):
    location_resolved: str
    has_active_alerts: bool
    alerts: List[AlertItem]
    weather_context: Optional[WeatherSnapshot] = None
    checked_at: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
