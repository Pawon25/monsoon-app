import os
import sys
from pathlib import Path

# Ensure required env vars exist before app/config is imported anywhere.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("OPENWEATHER_API_KEY", "test-openweather-key")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")  # avoid flaky rate-limit hits in tests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_weather_snapshot():
    from app.models.schemas import WeatherSnapshot

    return WeatherSnapshot(
        location_resolved="Bengaluru, Karnataka, IN",
        temperature_c=24.5,
        feels_like_c=25.0,
        humidity_pct=88,
        wind_speed_ms=3.2,
        rain_mm_last_hour=2.0,
        condition="Rain",
        condition_description="moderate rain",
        fetched_at="2026-07-11T10:00:00+00:00",
    )
