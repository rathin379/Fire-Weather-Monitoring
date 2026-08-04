/* Read-only Fire Weather dashboard. It only fetches persisted PostgreSQL records. */
(() => {
  "use strict";

  const API_URL = window.FIRE_API_URL || "/api/fire/telemetry";
  const MAX_TIMELINE_POINTS = 40;
  const chartInstances = {};
  let currentEvents = [];

  const byId = (id) => document.getElementById(id);
  const numberOrNull = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const average = (values) => {
    const valid = values.filter((value) => value !== null && Number.isFinite(value));
    return valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null;
  };
  const formatNumber = (value, digits = 1) => value === null || value === undefined ? "--" : Number(value).toFixed(digits);
  const formatDate = (value) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "--" : date.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  };
  const formatRange = (first, last) => first && last ? `${formatDate(first)} to ${formatDate(last)}` : "No matching observations";
  const valueWithUnit = (value, unit, digits = 1) => `${formatNumber(value, digits)}${value === null || value === undefined ? "" : ` ${unit}`}`;

  function setKpi(id, value, unit = "", digits = 1) {
    const node = byId(id);
    node.replaceChildren();
    node.append(document.createTextNode(formatNumber(value, digits)));
    if (value !== null && value !== undefined && unit) {
      const suffix = document.createElement("span");
      suffix.className = "unit";
      suffix.textContent = unit;
      node.append(suffix);
    }
  }

  function readFilters() {
    const params = new URLSearchParams({ limit: "5000", window: byId("windowSelect").value, scenario: byId("scenarioSelect").value });
    for (const [inputId, name] of [["startInput", "start"], ["endInput", "end"]]) {
      const value = byId(inputId).value;
      if (value) {
        const date = new Date(value);
        if (!Number.isNaN(date.getTime())) params.set(name, date.toISOString());
      }
    }
    return params;
  }

  function makeBuckets(events) {
    const ordered = [...events].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    if (!ordered.length) return [];
    const count = Math.min(MAX_TIMELINE_POINTS, ordered.length);
    return Array.from({ length: count }, (_, index) => {
      const start = Math.floor(index * ordered.length / count);
      const end = Math.max(start + 1, Math.floor((index + 1) * ordered.length / count));
      const slice = ordered.slice(start, end);
      const last = slice[slice.length - 1];
      return {
        label: formatDate(last.timestamp),
        risk: average(slice.map((event) => numberOrNull(event.risk_score))),
        temperature: average(slice.map((event) => numberOrNull(event.temperature))),
        humidity: average(slice.map((event) => numberOrNull(event.humidity))),
        wind: average(slice.map((event) => numberOrNull(event.wind_speed_ms))),
      };
    });
  }

  function chartOptions(extra = {}) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#9ca3af", boxWidth: 10, padding: 14, font: { size: 10 } } },
        tooltip: { backgroundColor: "#10131a", titleColor: "#f3f4f6", bodyColor: "#d1d5db", borderColor: "#303744", borderWidth: 1 },
      },
      scales: {
        x: { ticks: { color: "#6b7280", maxRotation: 0, autoSkip: true, maxTicksLimit: 7, font: { size: 9 } }, grid: { color: "rgba(255,255,255,.04)" } },
        y: { ticks: { color: "#6b7280", font: { size: 9 } }, grid: { color: "rgba(255,255,255,.04)" } },
      },
      ...extra,
    };
  }

  function replaceChart(id, config) {
    if (chartInstances[id]) chartInstances[id].destroy();
    if (typeof window.Chart === "function") chartInstances[id] = new window.Chart(byId(id), config);
  }

  function renderCharts(events) {
    const valid = events.filter((event) => event.data_quality === "valid");
    const buckets = makeBuckets(valid);
    const labels = buckets.map((bucket) => bucket.label);
    byId("riskEmpty").hidden = buckets.some((bucket) => bucket.risk !== null);
    byId("driversEmpty").hidden = buckets.some((bucket) => bucket.temperature !== null || bucket.humidity !== null || bucket.wind !== null);
    replaceChart("riskChart", {
      type: "line",
      data: { labels, datasets: [{ label: "Screening risk / 100", data: buckets.map((bucket) => bucket.risk), borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,.13)", fill: true, tension: .32, pointRadius: 1.5, spanGaps: true }] },
      options: chartOptions({ scales: { x: chartOptions().scales.x, y: { ...chartOptions().scales.y, min: 0, max: 100 } } }),
    });
    replaceChart("driversChart", {
      type: "line",
      data: { labels, datasets: [
        { label: "Temperature deg C", data: buckets.map((bucket) => bucket.temperature), borderColor: "#fb923c", tension: .32, pointRadius: 1.2, yAxisID: "temperature" },
        { label: "Humidity %", data: buckets.map((bucket) => bucket.humidity), borderColor: "#60a5fa", tension: .32, pointRadius: 1.2, yAxisID: "humidity" },
        { label: "Wind m/s", data: buckets.map((bucket) => bucket.wind), borderColor: "#facc15", tension: .32, pointRadius: 1.2, yAxisID: "temperature" },
      ] },
      options: chartOptions({ scales: {
        x: chartOptions().scales.x,
        temperature: { ...chartOptions().scales.y, position: "left" },
        humidity: { ...chartOptions().scales.y, position: "right", min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { color: "#60a5fa", font: { size: 9 } } },
      } }),
    });

    const scenarios = ["normal", "elevated_dry", "red_flag", "sensor_fault"];
    const colors = ["#34d399", "#fbbf24", "#ef4444", "#a78bfa"];
    const counts = scenarios.map((scenario) => events.filter((event) => event.scenario === scenario).length);
    byId("scenarioEmpty").hidden = counts.some((count) => count > 0);
    replaceChart("scenarioChart", {
      type: "doughnut",
      data: { labels: scenarios.map((scenario) => scenario.replaceAll("_", " ")), datasets: [{ data: counts, backgroundColor: colors, borderWidth: 0 }] },
      options: { responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { position: "right", labels: { color: "#9ca3af", boxWidth: 10, padding: 12, font: { size: 10 } } } } },
    });
  }

  function renderAlerts(events) {
    const feed = byId("alertFeed");
    feed.replaceChildren();
    const high = events.filter((event) => ["high", "extreme"].includes(event.risk_level));
    const faults = events.filter((event) => event.data_quality === "invalid");
    const lowestHumidity = Math.min(...events.filter((event) => event.data_quality === "valid").map((event) => numberOrNull(event.humidity)).filter((value) => value !== null), Infinity);
    const alerts = [];
    if (high.length) alerts.push(["critical", `${high.length} high or extreme fire-weather event${high.length === 1 ? "" : "s"} in the selected window.`, "Review the risk trend and recent events."]);
    if (faults.length) alerts.push(["warning", `${faults.length} sensor-fault event${faults.length === 1 ? "" : "s"} excluded from risk and ML export.`, "Inspect humidity/wind sensor health."]);
    if (Number.isFinite(lowestHumidity) && lowestHumidity < 20) alerts.push(["warning", `Minimum valid relative humidity is ${lowestHumidity.toFixed(1)}%.`, "Dry air materially raises spread potential."]);
    if (!alerts.length) alerts.push(["info", "No active high-risk or data-quality attention items in this window.", "Continue monitoring the next refresh."]);
    for (const [level, message, detail] of alerts) {
      const item = document.createElement("div");
      item.className = `alert-item ${level}`;
      item.innerHTML = '<span class="alert-dot"></span><div><div class="alert-msg"></div><div class="alert-time"></div></div>';
      item.querySelector(".alert-msg").textContent = message;
      item.querySelector(".alert-time").textContent = detail;
      feed.append(item);
    }
  }

  function renderTable(events) {
    const body = byId("recentEventsBody");
    body.replaceChildren();
    const newest = [...events].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)).slice(0, 12);
    if (!newest.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 8;
      cell.textContent = "No PostgreSQL events match this filter.";
      row.append(cell);
      body.append(row);
      return;
    }
    for (const event of newest) {
      const row = document.createElement("tr");
      const risk = event.risk_score === null || event.risk_score === undefined ? "unknown" : `${formatNumber(event.risk_score, 1)} ${event.risk_level}`;
      const fields = [
        formatDate(event.timestamp),
        event.scenario.replaceAll("_", " "),
        valueWithUnit(numberOrNull(event.temperature), "deg C", 1),
        valueWithUnit(numberOrNull(event.humidity), "%", 1),
        `${valueWithUnit(numberOrNull(event.wind_speed_ms), "m/s", 1)} / ${valueWithUnit(numberOrNull(event.wind_gust_ms), "m/s", 1)}`,
        valueWithUnit(numberOrNull(event.fuel_moisture_pct), "%", 1),
        risk,
        event.status,
      ];
      fields.forEach((field, index) => {
        const cell = document.createElement("td");
        cell.textContent = field;
        if (index === 6) cell.className = `risk-${event.risk_level || "unknown"}`;
        row.append(cell);
      });
      body.append(row);
    }
  }

  function render(payload) {
    currentEvents = payload.events || [];
    const valid = currentEvents.filter((event) => event.data_quality === "valid");
    const risk = average(valid.map((event) => numberOrNull(event.risk_score)));
    const maxGust = Math.max(...valid.map((event) => numberOrNull(event.wind_gust_ms)).filter((value) => value !== null), -Infinity);
    const minFuel = Math.min(...valid.map((event) => numberOrNull(event.fuel_moisture_pct)).filter((value) => value !== null), Infinity);
    const summary = payload.summary || {};
    setKpi("averageRisk", risk, "/ 100", 1);
    setKpi("highRiskEvents", numberOrNull(summary.high_risk_events) ?? 0, "events", 0);
    setKpi("maxWindGust", Number.isFinite(maxGust) ? maxGust : null, "m/s", 1);
    setKpi("minFuelMoisture", Number.isFinite(minFuel) ? minFuel : null, "%", 1);
    byId("averageRiskNote").textContent = `${valid.length.toLocaleString()} valid observations`;
    byId("highRiskNote").textContent = `${Number(summary.invalid_events || 0).toLocaleString()} sensor-fault events excluded`;
    byId("maxWindNote").textContent = "Maximum sustained-gust pair in the window";
    byId("fuelNote").textContent = "Synthetic fine-fuel moisture proxy";
    byId("scopeLabel").textContent = `${currentEvents.length.toLocaleString()} displayed of ${Number(summary.count || 0).toLocaleString()} matching records | ${formatRange(summary.first_observation, summary.last_observation)}`;
    byId("driverMeta").textContent = `${valid.length.toLocaleString()} valid records`;
    byId("coverageMeta").textContent = `${currentEvents.length.toLocaleString()} records`;
    byId("eventCount").textContent = `${currentEvents.length.toLocaleString()} events`;
    renderCharts(currentEvents);
    renderAlerts(currentEvents);
    renderTable(currentEvents);
  }

  async function refresh() {
    const started = performance.now();
    try {
      const response = await fetch(`${API_URL}?${readFilters()}`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
      render(body);
      byId("connectionDot").className = "connection-dot connected";
      byId("connectionTitle").textContent = "Connected to PostgreSQL";
      byId("connectionStatus").textContent = `Read-only load completed in ${Math.round(performance.now() - started)} ms.`;
      byId("refreshLabel").textContent = `Last refreshed ${new Date().toLocaleTimeString()} | automatic refresh every 10 seconds`;
    } catch (error) {
      byId("connectionDot").className = "connection-dot error";
      byId("connectionTitle").textContent = "Database connection unavailable";
      byId("connectionStatus").textContent = `${error.message} Check POSTGRES_DSN and restart fire_api.py.`;
      byId("refreshLabel").textContent = "No data is fabricated while the database is unavailable.";
    }
  }

  byId("applyFilters").addEventListener("click", () => {
    if (byId("startInput").value || byId("endInput").value) byId("windowSelect").value = "all";
    refresh();
  });
  byId("refreshDatabase").addEventListener("click", refresh);
  window.setInterval(refresh, 10000);
  refresh();
})();