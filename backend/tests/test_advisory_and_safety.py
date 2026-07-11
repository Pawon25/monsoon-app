from unittest.mock import AsyncMock, patch


def test_travel_advisory_success(client, sample_weather_snapshot):
    payload = {
        "location": {"city": "Pune", "country": "IN"},
        "destination": {"city": "Mumbai", "country": "IN"},
        "output_language": "Marathi",
        "mode_of_travel": "car",
        "travel_date": "2026-07-15",
    }
    with patch(
        "app.routes.advisory.get_current_weather", new=AsyncMock(return_value=sample_weather_snapshot)
    ), patch("app.routes.advisory.generate_text", new=AsyncMock(return_value="Travel advisory text")):
        resp = client.post("/api/travel-advisory", json=payload)
    assert resp.status_code == 200
    assert resp.json()["content"] == "Travel advisory text"


def test_safety_recommendation_success(client, sample_weather_snapshot):
    payload = {
        "location": {"city": "Kochi", "state": "Kerala", "country": "IN"},
        "output_language": "Malayalam",
        "household": {"household_size": 3, "has_elderly": True},
        "situation": "Water is entering the ground floor.",
    }
    with patch(
        "app.routes.safety.get_current_weather", new=AsyncMock(return_value=sample_weather_snapshot)
    ), patch("app.routes.safety.generate_text", new=AsyncMock(return_value="Evacuate now: ...")):
        resp = client.post("/api/safety-recommendation", json=payload)
    assert resp.status_code == 200
    assert "Evacuate" in resp.json()["content"]


def test_safety_recommendation_missing_household_uses_default(client, sample_weather_snapshot):
    payload = {
        "location": {"city": "Kochi", "country": "IN"},
        "household": {},
    }
    with patch(
        "app.routes.safety.get_current_weather", new=AsyncMock(return_value=sample_weather_snapshot)
    ), patch("app.routes.safety.generate_text", new=AsyncMock(return_value="Guidance")):
        resp = client.post("/api/safety-recommendation", json=payload)
    assert resp.status_code == 200
