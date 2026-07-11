/**
 * Varsha Sahayak — frontend application logic.
 *
 * Stateless/no-auth by design: all context (location, language, household
 * details) lives in the DOM/JS state for the current session only. Every
 * Claude-backed feature call goes through the FastAPI backend; no API keys
 * ever touch this file.
 */
"use strict";

// Set this to your deployed Render backend URL before deploying to Netlify.
// Left as localhost for local development.
const API_BASE_URL = window.API_BASE_URL || "http://localhost:8000";

const ALERT_POLL_INTERVAL_MS = 15 * 60 * 1000; // 15 minutes, matches backend default

/** @type {{city: string, state: string, country: string} | null} */
let currentLocation = null;
let alertPollHandle = null;

// ---------------------------------------------------------------------
// Generic API helpers
// ---------------------------------------------------------------------

/**
 * POST JSON to the backend and return the parsed response.
 * Throws an Error with a user-friendly message on any failure.
 */
async function apiPost(path, body) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (networkErr) {
    throw new Error("Could not reach the server. Check your connection and try again.");
  }
  return handleApiResponse(response);
}

/** GET from the backend with query params and return the parsed response. */
async function apiGet(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ).toString();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}${query ? `?${query}` : ""}`);
  } catch (networkErr) {
    throw new Error("Could not reach the server. Check your connection and try again.");
  }
  return handleApiResponse(response);
}

async function handleApiResponse(response) {
  let data = null;
  try {
    data = await response.json();
  } catch {
    // no-op: some error responses may not have a JSON body
  }
  if (!response.ok) {
    const detail = data?.detail || data?.error || `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return data;
}

// ---------------------------------------------------------------------
// Shared context (location + language)
// ---------------------------------------------------------------------

function getSelectedLanguage() {
  const select = document.getElementById("language");
  if (select.value === "other") {
    const custom = document.getElementById("custom-language").value.trim();
    return custom || "English";
  }
  return select.value;
}

function requireLocation() {
  if (!currentLocation) {
    throw new Error("Please set your city above first.");
  }
  return currentLocation;
}

document.getElementById("language").addEventListener("change", (e) => {
  document.getElementById("custom-language-field").hidden = e.target.value !== "other";
});

document.getElementById("context-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const city = document.getElementById("city").value.trim();
  const state = document.getElementById("state").value.trim();
  const statusEl = document.getElementById("context-status");

  if (!city) return;

  currentLocation = { city, state, country: "IN" };
  statusEl.dataset.state = "";
  statusEl.textContent = "Fetching live weather...";

  try {
    const weather = await apiGet("/api/weather", { city, state, country: "IN" });
    renderWeather(weather);
    statusEl.textContent = `Location set to ${weather.location_resolved}.`;
    restartAlertPolling();
  } catch (err) {
    statusEl.dataset.state = "error";
    statusEl.textContent = `Could not fetch weather: ${err.message} You can still use the other features.`;
  }
});

// ---------------------------------------------------------------------
// Weather card (Feature 2: weather-aware guidance grounding)
// ---------------------------------------------------------------------

function renderWeather(weather) {
  const card = document.getElementById("weather-card");
  card.innerHTML = "";

  const headline = document.createElement("p");
  headline.className = "weather-headline";
  headline.textContent = `${weather.location_resolved} — ${weather.condition_description || weather.condition || "conditions unavailable"}`;
  card.appendChild(headline);

  const metrics = [
    ["Temperature", weather.temperature_c != null ? `${weather.temperature_c}°C` : "—"],
    ["Feels like", weather.feels_like_c != null ? `${weather.feels_like_c}°C` : "—"],
    ["Humidity", weather.humidity_pct != null ? `${weather.humidity_pct}%` : "—"],
    ["Wind", weather.wind_speed_ms != null ? `${weather.wind_speed_ms} m/s` : "—"],
    ["Rain (1h)", weather.rain_mm_last_hour != null ? `${weather.rain_mm_last_hour} mm` : "0 mm"],
  ];

  for (const [label, value] of metrics) {
    const m = document.createElement("div");
    m.className = "weather-metric";
    m.innerHTML = `<span class="label">${label}</span><span class="value">${value}</span>`;
    card.appendChild(m);
  }
}

// ---------------------------------------------------------------------
// Real-time alerts (Feature 7)
// ---------------------------------------------------------------------

function restartAlertPolling() {
  if (alertPollHandle) clearInterval(alertPollHandle);
  checkAlertsNow();
  alertPollHandle = setInterval(checkAlertsNow, ALERT_POLL_INTERVAL_MS);
}

async function checkAlertsNow() {
  if (!currentLocation) return;
  try {
    const data = await apiGet("/api/alerts", {
      city: currentLocation.city,
      state: currentLocation.state,
      country: currentLocation.country,
      output_language: getSelectedLanguage(),
    });
    if (data.has_active_alerts && data.alerts.length) {
      showAlertBanner(data.alerts);
    } else {
      hideAlertBanner();
    }
  } catch {
    // Silent failure on background polling — don't interrupt the user
    // with a banner error for a background check. Feature degrades quietly.
  }
}

function showAlertBanner(alerts) {
  const banner = document.getElementById("alert-banner");
  const content = document.getElementById("alert-banner-content");
  content.innerHTML = "";
  for (const a of alerts) {
    const block = document.createElement("div");
    block.innerHTML = `<strong>[${a.phase.toUpperCase()} · ${a.severity.toUpperCase()}] ${escapeHtml(a.headline)}</strong>${escapeHtml(a.message)}`;
    content.appendChild(block);
  }
  banner.hidden = false;
}

function hideAlertBanner() {
  document.getElementById("alert-banner").hidden = true;
}

document.getElementById("alert-banner-dismiss").addEventListener("click", hideAlertBanner);

// ---------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------

document.querySelectorAll(".tab").forEach((tabBtn) => {
  tabBtn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.setAttribute("aria-selected", "false"));
    document.querySelectorAll(".tab-panel").forEach((p) => (p.hidden = true));
    tabBtn.setAttribute("aria-selected", "true");
    document.getElementById(`tab-${tabBtn.dataset.tab}`).hidden = false;
  });
});

// ---------------------------------------------------------------------
// Result rendering helpers
// ---------------------------------------------------------------------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function renderLoading(container, message) {
  container.innerHTML = `<p class="loading-text">${escapeHtml(message)}</p>`;
}

function renderTextResult(container, data) {
  const card = document.createElement("div");
  card.className = "result-card";
  card.textContent = data.content;
  container.innerHTML = "";
  container.appendChild(card);
}

function renderChecklistResult(container, data) {
  container.innerHTML = "";
  const list = document.createElement("ul");
  list.className = "checklist-list";
  for (const item of data.items) {
    const li = document.createElement("li");
    li.className = "checklist-item";
    li.dataset.priority = item.priority;
    li.innerHTML = `<span class="category-tag">${escapeHtml(item.category)}</span><span>${escapeHtml(item.item)}</span>`;
    list.appendChild(li);
  }
  container.appendChild(list);
}

function renderError(container, err) {
  container.innerHTML = `<p class="result-error">Something went wrong: ${escapeHtml(err.message)}</p>`;
}

async function withSubmitState(form, container, loadingMessage, task) {
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  renderLoading(container, loadingMessage);
  try {
    await task();
  } catch (err) {
    renderError(container, err);
  } finally {
    btn.disabled = false;
  }
}

// ---------------------------------------------------------------------
// Feature 1: Preparedness plan
// ---------------------------------------------------------------------

document.getElementById("plan-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const container = document.getElementById("plan-result");
  await withSubmitState(form, container, "Generating your personalized plan...", async () => {
    const location = requireLocation();
    const payload = {
      location,
      output_language: getSelectedLanguage(),
      household: {
        household_size: Number(document.getElementById("plan-household-size").value) || 1,
        has_children: document.getElementById("plan-children").checked,
        has_elderly: document.getElementById("plan-elderly").checked,
        has_pets: document.getElementById("plan-pets").checked,
        has_disabled_members: document.getElementById("plan-disabled").checked,
        dwelling_type: document.getElementById("plan-dwelling").value.trim() || null,
        risk_level: document.getElementById("plan-risk").value,
        additional_notes: document.getElementById("plan-notes").value.trim() || null,
      },
    };
    const data = await apiPost("/api/preparedness-plan", payload);
    renderTextResult(container, data);
  });
});

// ---------------------------------------------------------------------
// Feature 3: Checklist
// ---------------------------------------------------------------------

document.getElementById("checklist-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const container = document.getElementById("checklist-result");
  await withSubmitState(form, container, "Building your checklist...", async () => {
    const location = requireLocation();
    const payload = {
      location,
      output_language: getSelectedLanguage(),
      household: {
        household_size: Number(document.getElementById("checklist-household-size").value) || 1,
        has_children: document.getElementById("checklist-children").checked,
        has_elderly: document.getElementById("checklist-elderly").checked,
        has_pets: document.getElementById("checklist-pets").checked,
        risk_level: document.getElementById("checklist-risk").value,
      },
    };
    const data = await apiPost("/api/checklist", payload);
    renderChecklistResult(container, data);
  });
});

// ---------------------------------------------------------------------
// Feature 4: Travel advisory
// ---------------------------------------------------------------------

document.getElementById("advisory-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const container = document.getElementById("advisory-result");
  await withSubmitState(form, container, "Checking route conditions...", async () => {
    const location = requireLocation();
    const destCity = document.getElementById("advisory-destination-city").value.trim();
    if (!destCity) throw new Error("Please enter a destination city.");
    const payload = {
      location,
      destination: {
        city: destCity,
        state: document.getElementById("advisory-destination-state").value.trim() || null,
        country: "IN",
      },
      output_language: getSelectedLanguage(),
      mode_of_travel: document.getElementById("advisory-mode").value || null,
      travel_date: document.getElementById("advisory-date").value || null,
    };
    const data = await apiPost("/api/travel-advisory", payload);
    renderTextResult(container, data);
  });
});

// ---------------------------------------------------------------------
// Feature 5: Safety recommendation
// ---------------------------------------------------------------------

document.getElementById("safety-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const container = document.getElementById("safety-result");
  await withSubmitState(form, container, "Getting immediate guidance...", async () => {
    const location = requireLocation();
    const payload = {
      location,
      output_language: getSelectedLanguage(),
      household: {
        household_size: Number(document.getElementById("safety-household-size").value) || 1,
        has_children: document.getElementById("safety-children").checked,
        has_elderly: document.getElementById("safety-elderly").checked,
        has_disabled_members: document.getElementById("safety-disabled").checked,
      },
      situation: document.getElementById("safety-situation").value.trim() || null,
    };
    const data = await apiPost("/api/safety-recommendation", payload);
    renderTextResult(container, data);
  });
});
