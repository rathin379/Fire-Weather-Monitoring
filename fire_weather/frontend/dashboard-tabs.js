/* Adds Live Event Stream and Machine Learning tabs without changing Analytics. */
(() => {
  "use strict";

  const STREAM_URL = window.FIRE_STREAM_URL || "/api/fire/stream";
  const STREAM_FALLBACK_URL = "/api/fire/telemetry?window=all&scenario=all&limit=30";
  const LIVE_STREAM_URL = window.FIRE_LIVE_STREAM_URL || "/api/fire/stream/live";
  const ML_URL = window.FIRE_ML_API_URL || "/api/ml";
  const DIRECT_ML_URL = "http://127.0.0.1:5001";
  let activePanel = "panel-analytics";
  let streamPaused = false;
  let liveEvents = [];
  let liveSource = null;
  let lastLiveId = 0;
  const byId = (id) => document.getElementById(id);
  const formatNumber = (value, digits = 1) => value === null || value === undefined ? "--" : Number(value).toFixed(digits);
  const formatDate = (value, seconds = false) => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "--";
    return date.toLocaleString([], { month:"short", day:"2-digit", hour:"2-digit", minute:"2-digit", ...(seconds ? { second:"2-digit" } : {}) });
  };
  const friendly = (value, fallback = "unknown") => String(value || fallback).replaceAll("_", " ");

  function activate(panelId) {
    activePanel = panelId;
    document.querySelectorAll(".dashboard-tab").forEach((button) => {
      const selected = button.dataset.panel === panelId;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-selected", String(selected));
    });
    document.querySelectorAll(".dashboard-panel").forEach((panel) => {
      panel.hidden = panel.id !== panelId;
    });
    if (panelId === "panel-live") refreshStream();
    if (panelId === "panel-ml") checkMlHealth();
  }

  function addMetric(container, label, value) {
    const item = document.createElement("div");
    item.className = "event-metric";
    const name = document.createElement("span");
    name.textContent = label;
    const detail = document.createElement("strong");
    detail.textContent = value;
    item.append(name, detail);
    container.append(item);
  }

  function renderStream(events) {
    const feed = byId("liveEventFeed");
    feed.replaceChildren();
    byId("liveCount").textContent = events.length.toLocaleString();
    byId("liveNewest").textContent = events.length ? formatDate(events[0].timestamp, true) : "--";
    byId("liveState").textContent = streamPaused ? "Paused" : "Live";
    if (!events.length) {
      const empty = document.createElement("div");
      empty.className = "panel-empty";
      empty.textContent = "No persisted events yet. Start the subscriber and generator in separate terminals.";
      feed.append(empty);
      return;
    }
    events.forEach((event) => {
      const card = document.createElement("article");
      const color = event.data_quality === "invalid" ? "#a78bfa" : event.risk_level === "extreme" ? "#ef4444" : event.risk_level === "high" ? "#f97316" : event.risk_level === "elevated" ? "#fbbf24" : "#34d399";
      card.className = "event-card";
      card.style.setProperty("--event-color", color);
      const head = document.createElement("div");
      head.className = "event-card-head";
      const device = document.createElement("strong");
      device.textContent = event.device_id || "Unknown device";
      const time = document.createElement("span");
      time.textContent = formatDate(event.timestamp, true);
      const badges = document.createElement("div");
      badges.className = "event-badges";
      [friendly(event.scenario), friendly(event.risk_level), friendly(event.data_quality)].forEach((text) => {
        const badge = document.createElement("span");
        badge.className = "event-badge";
        badge.textContent = text;
        badges.append(badge);
      });
      head.append(device, time, badges);
      const metrics = document.createElement("div");
      metrics.className = "event-metrics";
      addMetric(metrics, "Risk", event.risk_score === null ? "--" : `${formatNumber(event.risk_score)} / 100`);
      addMetric(metrics, "Temperature", `${formatNumber(event.temperature)} deg C`);
      addMetric(metrics, "Humidity", event.humidity === null ? "--" : `${formatNumber(event.humidity)} %`);
      addMetric(metrics, "Pressure", `${formatNumber(event.pressure_mbar, 1)} mbar`);
      addMetric(metrics, "Wind", `${formatNumber(event.wind_speed_ms)} m/s`);
      addMetric(metrics, "Gust", `${formatNumber(event.wind_gust_ms)} m/s`);
      addMetric(metrics, "Fuel proxy", `${formatNumber(event.fuel_moisture_pct)} %`);
      addMetric(metrics, "Status", friendly(event.status));
      card.append(head, metrics);
      feed.append(card);
    });
  }

  function closeLiveStream() {
    if (liveSource) liveSource.close();
    liveSource = null;
  }

  function addLiveEvent(event) {
    const eventId = Number(event.id) || 0;
    lastLiveId = Math.max(lastLiveId, eventId);
    liveEvents = [event, ...liveEvents.filter((item) => Number(item.id) !== eventId)].slice(0, 30);
    renderStream(liveEvents);
    byId("liveStatus").textContent = `Event received ${new Date().toLocaleTimeString()} | persistent connection`;
  }

  function connectLiveStream() {
    closeLiveStream();
    if (streamPaused || typeof EventSource === "undefined") return;
    liveSource = new EventSource(`${LIVE_STREAM_URL}?after_id=${lastLiveId}`);
    liveSource.addEventListener("open", () => {
      byId("liveStatus").textContent = "Connected | new PostgreSQL events appear immediately";
      byId("liveState").textContent = "Live";
    });
    liveSource.addEventListener("telemetry", (message) => {
      try {
        addLiveEvent(JSON.parse(message.data));
      } catch (error) {
        byId("liveStatus").textContent = `Live event rejected: ${error.message}`;
      }
    });
    liveSource.addEventListener("error", () => {
      if (!streamPaused) byId("liveStatus").textContent = "Live connection interrupted | reconnecting automatically";
    });
  }

  async function refreshStream() {
    if (streamPaused) return;
    closeLiveStream();
    try {
      let response = await fetch(`${STREAM_URL}?limit=30`, { cache:"no-store" });
      let body;
      if (response.ok) {
        body = await response.json();
      } else {
        response = await fetch(STREAM_FALLBACK_URL, { cache:"no-store" });
        body = await response.json();
        if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
        body.events = (body.events || []).slice(-30).reverse();
      }
      liveEvents = body.events || [];
      lastLiveId = liveEvents.reduce((highest, event) => Math.max(highest, Number(event.id) || 0), 0);
      renderStream(liveEvents);
      byId("liveStatus").textContent = "Opening persistent live connection...";
      connectLiveStream();
    } catch (error) {
      byId("liveStatus").textContent = `Live stream unavailable: ${error.message}`;
      renderStream([]);
    }
  }
  async function fetchMl(path, options = {}) {
    const response = await fetch(`${ML_URL}${path}`, options);
    const contentType = response.headers.get("Content-Type") || "";
    if (response.status === 404 || response.status === 501 || !contentType.includes("application/json")) {
      return fetch(`${DIRECT_ML_URL}${path}`, options);
    }
    return response;
  }
  function setMlStatus(ok, text) {
    const chip = byId("mlServiceStatus");
    chip.className = `ml-service-chip ${ok ? "connected" : "error"}`;
    chip.textContent = text;
  }

  async function checkMlHealth() {
    try {
      const response = await fetchMl("/health", { cache:"no-store" });
      const body = await response.json().catch(() => ({ error:"Restart the dashboard API to enable the ML connection." }));
      if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
      setMlStatus(true, `ML connected | model ${body.model_version}`);
    } catch (error) {
      setMlStatus(false, error.message || "ML service unavailable");
    }
  }

  const explanations = {
    humidity_regression: "Estimates relative humidity from temperature and pressure using linear regression.",
    low_humidity_classifier: "Estimates the probability that relative humidity is below 30% using logistic regression.",
    pressure_risk_classifier: "Uses temperature plus pressure change per hour. The service retrieves the prior valid event for this device from PostgreSQL.",
  };

  function updateModelExplanation() {
    const task = byId("mlModel").value;
    byId("mlExplanation").textContent = explanations[task];
  }

  function appendDetail(list, label, value) {
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = value;
    list.append(term, detail);
  }

  function renderPrediction(body) {
    const result = byId("mlResult");
    result.replaceChildren();
    const label = document.createElement("p");
    label.className = "result-label";
    label.textContent = body.prediction.label;
    const value = document.createElement("strong");
    value.className = "result-value";
    value.textContent = body.prediction.probability_pct !== undefined ? `${formatNumber(body.prediction.probability_pct, 2)}% probability` : `${formatNumber(body.prediction.value, 2)} ${body.prediction.unit || ""}`;
    const interpretation = document.createElement("p");
    interpretation.textContent = body.prediction.interpretation;
    const details = document.createElement("dl");
    appendDetail(details, "Model", body.model_version);
    appendDetail(details, "Task", body.task_name);
    appendDetail(details, "Temperature", `${formatNumber(body.event.temperature)} deg C`);
    appendDetail(details, "Pressure", `${formatNumber(body.event.pressure_mbar, 2)} mbar`);
    if (body.context?.pressure_rate_mbar_per_hour !== undefined) {
      appendDetail(details, "Pressure change", `${formatNumber(body.context.pressure_rate_mbar_per_hour, 3)} mbar/hour`);
      appendDetail(details, "Context", body.context.source);
    }
    result.append(label, value, interpretation, details);
  }

  async function submitPrediction(event) {
    event.preventDefault();
    const button = byId("mlSubmit");
    const message = byId("mlMessage");
    const timestamp = new Date(byId("mlTimestamp").value);
    if (Number.isNaN(timestamp.getTime())) {
      message.className = "form-message error";
      message.textContent = "Enter a valid event date and time.";
      return;
    }
    button.disabled = true;
    button.textContent = "Making prediction...";
    message.textContent = "";
    try {
      const response = await fetchMl("/predict", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body:JSON.stringify({
          model:byId("mlModel").value,
          event:{
            device_id:byId("mlDevice").value.trim(),
            timestamp:timestamp.toISOString(),
            temperature:Number(byId("mlTemperature").value),
            pressure_mbar:Number(byId("mlPressure").value),
          },
        }),
      });
      const body = await response.json().catch(() => ({ error:"Restart fire_api.py, then start ml_service.py in Terminal 4." }));
      if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
      renderPrediction(body);
      message.className = "form-message success";
      message.textContent = "Prediction received from the standalone ML service.";
      setMlStatus(true, `ML connected | model ${body.model_version}`);
    } catch (error) {
      message.className = "form-message error";
      message.textContent = error.message || "ML service unavailable. Start ml_service.py in Terminal 4.";
      setMlStatus(false, "ML prediction failed");
    } finally {
      button.disabled = false;
      button.textContent = "Make prediction";
    }
  }

  document.querySelectorAll(".dashboard-tab").forEach((button) => button.addEventListener("click", () => activate(button.dataset.panel)));
  byId("liveRefresh").addEventListener("click", refreshStream);
  byId("livePause").addEventListener("click", () => {
    streamPaused = !streamPaused;
    byId("livePause").textContent = streamPaused ? "Resume" : "Pause";
    byId("liveState").textContent = streamPaused ? "Paused" : "Live";
    if (streamPaused) closeLiveStream();
    else refreshStream();
  });
  byId("mlModel").addEventListener("change", updateModelExplanation);
  byId("mlForm").addEventListener("submit", submitPrediction);
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  byId("mlTimestamp").value = now.toISOString().slice(0, 19);
  updateModelExplanation();
  window.setInterval(() => { if (activePanel === "panel-ml") checkMlHealth(); }, 15000);
})();
