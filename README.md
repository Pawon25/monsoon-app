# Varsha Sahayak — Monsoon Preparedness & Citizen Assistance

GenAI-powered monsoon preparedness assistant built for the H2S PromptWars main challenge. No login required — stateless, session-based use for the general public.

## Features

1. **Personalized preparedness plan** — household + location → Claude-generated tailored plan.
2. **Weather-aware guidance** — every Claude call is grounded in live OpenWeatherMap conditions for the user's location.
3. **Emergency checklist generator** — structured, prioritized checklist based on household + risk context.
4. **Travel advisories** — Claude-generated advisory grounded in live weather at the destination.
5. **Safety recommendations** — situational, immediately actionable guidance (distinct from the general plan).
6. **Multilingual assistance** — every generation call takes an `output_language`; English, Hindi, Kannada, Marathi, Bengali, Tamil, Telugu, and Malayalam are first-class UI options, and the field accepts any language name.
7. **Real-time alerts** — the frontend polls `/api/alerts` every 15 minutes; the backend combines the weather provider's severe-alert feed with a current-conditions heuristic, then has Claude localize/phase-tag the result (before/during/after).

## Project structure

```
monsoon-app/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, exception handlers
│   │   ├── config.py             # env-based settings
│   │   ├── models/schemas.py     # Pydantic request/response models
│   │   ├── routes/               # one router per feature
│   │   ├── services/             # claude_service, weather_service, cache
│   │   ├── prompts/templates.py  # all prompt construction, injection-guarded
│   │   └── middleware/           # sanitize.py, rate_limit.py
│   ├── tests/                    # pytest + TestClient, mocked external APIs
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html
    ├── css/style.css
    ├── js/config.js              # set API_BASE_URL here for deployment
    ├── js/app.js
    └── netlify.toml
```

## Local development

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY and OPENWEATHER_API_KEY
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API docs.

### Frontend

`frontend/js/config.js` already points at `http://localhost:8000` by default. Serve the folder with any static server, e.g.:

```bash
cd frontend
python -m http.server 5500
```

Visit `http://localhost:5500`.

### Tests

```bash
cd backend
pytest -v
```

## Deployment

### Backend → Render

1. Push this repo to GitHub.
2. New Web Service on Render, root directory `backend`.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env.example` (`ANTHROPIC_API_KEY`, `OPENWEATHER_API_KEY`, `ALLOWED_ORIGINS` — set this to your Netlify URL once deployed).

### Frontend → Netlify

1. New site from Git, base directory `frontend`, publish directory `frontend`.
2. Before deploying, edit `frontend/js/config.js` and set `window.API_BASE_URL` to your Render backend URL.
3. Deploy. `netlify.toml` already sets sensible security headers.

## Security notes

- API keys are read only from environment variables server-side (`app/config.py`); the frontend never sees them.
- All inputs are validated with Pydantic (length caps, ranges, enums).
- Free-text fields that reach a Claude prompt are sanitized and screened for common injection phrasing (`app/middleware/sanitize.py`) and wrapped in a delimited, explicitly-untrusted block inside every prompt (`app/prompts/templates.py`).
- CORS is scoped to `ALLOWED_ORIGINS` (comma-separated env var), not `*`.
- A simple in-memory rate limiter guards `/api/*` routes (`RATE_LIMIT_PER_MINUTE`, default 20/min per IP).

## Efficiency notes

- Weather lookups are cached server-side for `WEATHER_CACHE_TTL_SECONDS` (default 5 min) and geocoding results for 1 hour, so repeated requests for the same location don't re-hit OpenWeatherMap.
- The alerts endpoint only calls Claude when there's something to localize (active alert or heuristically severe conditions) — a calm-weather poll is a cheap weather-API-only check.
