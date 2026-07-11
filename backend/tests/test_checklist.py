from unittest.mock import AsyncMock, patch

from app.services.claude_service import ClaudeServiceError

VALID_PAYLOAD = {
    "location": {"city": "Chennai", "state": "Tamil Nadu", "country": "IN"},
    "output_language": "Tamil",
    "household": {
        "household_size": 2,
        "has_elderly": True,
        "risk_level": "high",
    },
}

VALID_CLAUDE_JSON = [
    {"category": "Emergency Kit", "item": "Flashlight with spare batteries", "priority": "high"},
    {"category": "Documents", "item": "Waterproof pouch for ID cards", "priority": "normal"},
]


def test_checklist_success(client, sample_weather_snapshot):
    with patch(
        "app.routes.checklist.get_current_weather", new=AsyncMock(return_value=sample_weather_snapshot)
    ), patch("app.routes.checklist.generate_json", new=AsyncMock(return_value=VALID_CLAUDE_JSON)):
        resp = client.post("/api/checklist", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["category"] == "Emergency Kit"


def test_checklist_malformed_ai_json_returns_503(client, sample_weather_snapshot):
    with patch(
        "app.routes.checklist.get_current_weather", new=AsyncMock(return_value=sample_weather_snapshot)
    ), patch(
        "app.routes.checklist.generate_json",
        new=AsyncMock(return_value=[{"unexpected": "shape"}]),
    ):
        resp = client.post("/api/checklist", json=VALID_PAYLOAD)
    assert resp.status_code == 503


def test_checklist_ai_service_down_returns_503(client, sample_weather_snapshot):
    with patch(
        "app.routes.checklist.get_current_weather", new=AsyncMock(return_value=sample_weather_snapshot)
    ), patch(
        "app.routes.checklist.generate_json",
        new=AsyncMock(side_effect=ClaudeServiceError("down")),
    ):
        resp = client.post("/api/checklist", json=VALID_PAYLOAD)
    assert resp.status_code == 503
