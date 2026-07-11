from unittest.mock import AsyncMock, patch

from app.models.schemas import WeatherSnapshot
from app.services.claude_service import ClaudeServiceError


def _calm_weather():
    return WeatherSnapshot(
        location_resolved="Bengaluru, Karnataka, IN",
        temperature_c=27.0,
        condition="Clouds",
        condition_description="scattered clouds",
        rain_mm_last_hour=0.0,
        fetched_at="2026-07-11T10:00:00+00:00",
    )


def _severe_weather():
    return WeatherSnapshot(
        location_resolved="Mumbai, Maharashtra, IN",
        temperature_c=25.0,
        condition="Thunderstorm",
        condition_description="heavy thunderstorm",
        rain_mm_last_hour=15.0,
        fetched_at="2026-07-11T10:00:00+00:00",
    )


def test_alerts_no_active_alerts_when_calm(client):
    with patch("app.routes.alerts.get_current_weather", new=AsyncMock(return_value=_calm_weather())), patch(
        "app.routes.alerts.get_severe_alerts", new=AsyncMock(return_value=[])
    ):
        resp = client.get("/api/alerts", params={"city": "Bengaluru"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_active_alerts"] is False
    assert body["alerts"] == []


def test_alerts_synthesizes_from_severe_conditions(client):
    claude_json = [
        {"severity": "severe", "phase": "during", "headline": "Heavy rain alert", "message": "Stay indoors."}
    ]
    with patch("app.routes.alerts.get_current_weather", new=AsyncMock(return_value=_severe_weather())), patch(
        "app.routes.alerts.get_severe_alerts", new=AsyncMock(return_value=[])
    ), patch("app.routes.alerts.generate_json", new=AsyncMock(return_value=claude_json)):
        resp = client.get("/api/alerts", params={"city": "Mumbai", "output_language": "Hindi"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_active_alerts"] is True
    assert body["alerts"][0]["phase"] == "during"


def test_alerts_degrades_to_raw_passthrough_when_claude_fails(client):
    with patch("app.routes.alerts.get_current_weather", new=AsyncMock(return_value=_severe_weather())), patch(
        "app.routes.alerts.get_severe_alerts", new=AsyncMock(return_value=[])
    ), patch(
        "app.routes.alerts.generate_json", new=AsyncMock(side_effect=ClaudeServiceError("down"))
    ):
        resp = client.get("/api/alerts", params={"city": "Mumbai"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_active_alerts"] is True
    assert body["alerts"][0]["source"] == "weather-api-raw"


def test_alerts_missing_location_returns_422(client):
    resp = client.get("/api/alerts")
    assert resp.status_code == 422
