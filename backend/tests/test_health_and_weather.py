from unittest.mock import AsyncMock, patch

from app.services.weather_service import WeatherServiceError


def test_health_check(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["claude_configured"] is True
    assert body["weather_configured"] is True
    assert "English" in body["suggested_languages"]


def test_weather_missing_location_returns_422(client):
    resp = client.get("/api/weather")
    assert resp.status_code == 422


def test_weather_success(client, sample_weather_snapshot):
    with patch(
        "app.routes.weather.get_current_weather", new=AsyncMock(return_value=sample_weather_snapshot)
    ):
        resp = client.get("/api/weather", params={"city": "Bengaluru"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["location_resolved"] == "Bengaluru, Karnataka, IN"
    assert body["condition"] == "Rain"


def test_weather_upstream_failure_returns_502(client):
    with patch(
        "app.routes.weather.get_current_weather",
        new=AsyncMock(side_effect=WeatherServiceError("upstream down")),
    ):
        resp = client.get("/api/weather", params={"city": "Nowhereville"})
    assert resp.status_code == 502
    assert resp.json()["detail"] == "upstream down"
