"""Pure calculations used by the Fire Weather generator, subscriber, and export."""
from __future__ import annotations

import math
from typing import Any

SCENARIOS = ("normal", "elevated_dry", "red_flag", "sensor_fault", "mixed")
SCENARIO_ALIASES = {"outlier": "red_flag", "failure": "sensor_fault"}
RISK_LEVELS = ("low", "elevated", "high", "extreme", "unknown")


def canonical_scenario(value: str) -> str:
    """Convert older scenario names to the names used by this project."""
    normalized = SCENARIO_ALIASES.get(str(value).strip().lower(), str(value).strip().lower())
    if normalized not in SCENARIOS:
        raise ValueError(f"Unsupported scenario: {value}")
    return normalized


def is_number(value: Any) -> bool:
    """Check that a sensor value is a real, finite number."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def classify_scenario(event: dict[str, Any]) -> str:
    """Infer a scenario from measurements after the raw event is received."""
    required = ("temperature", "humidity", "wind_speed_ms", "fuel_moisture_pct")
    if not all(is_number(event.get(field)) for field in required):
        return "sensor_fault"
    temperature = float(event["temperature"])
    humidity = float(event["humidity"])
    wind = float(event["wind_speed_ms"])
    fuel = float(event["fuel_moisture_pct"])
    if temperature >= 32.0 and humidity <= 15.0 and wind >= 10.0 and fuel <= 8.0:
        return "red_flag"
    if temperature >= 27.0 and humidity <= 35.0 and wind >= 6.0 and fuel <= 15.0:
        return "elevated_dry"
    return "normal"

def saturation_vapor_pressure_mbar(temperature_c: float) -> float:
    """Estimate maximum vapor pressure at the supplied temperature."""
    return 6.112 * math.exp((17.62 * temperature_c) / (243.12 + temperature_c))


def dew_point_c(temperature_c: float, humidity_pct: float) -> float:
    """Calculate dew point from temperature and relative humidity."""
    humidity = max(0.1, min(100.0, humidity_pct))
    alpha = math.log(humidity / 100.0) + (17.62 * temperature_c) / (243.12 + temperature_c)
    return (243.12 * alpha) / (17.62 - alpha)


def potential_temperature_k(temperature_c: float, pressure_mbar: float) -> float:
    """Convert measured temperature to potential temperature in kelvin."""
    return (temperature_c + 273.15) * (1000.0 / pressure_mbar) ** 0.2854


def specific_humidity_gkg(pressure_mbar: float, vapor_pressure_mbar: float) -> float:
    """Calculate grams of water vapor per kilogram of air."""
    pressure_pa = pressure_mbar * 100.0
    vapor_pa = vapor_pressure_mbar * 100.0
    mixing_ratio = 0.622 * vapor_pa / max(1.0, pressure_pa - vapor_pa)
    return 1000.0 * mixing_ratio / (1.0 + mixing_ratio)


def jena_compatible_values(event: dict[str, Any]) -> dict[str, float | None]:
    """Derive the extra weather columns expected by the Jena training data."""
    temperature = event.get("temperature")
    pressure = event.get("pressure_mbar")
    humidity = event.get("humidity")
    wind = event.get("wind_speed_ms")
    gust = event.get("wind_gust_ms")
    direction = event.get("wind_dir_deg")
    density = event.get("air_density")
    if not all(is_number(value) for value in (temperature, pressure, humidity, wind, gust, direction, density)):
        return {"Tpot (K)": None, "Tdew (degC)": None, "VPmax (mbar)": None, "VPact (mbar)": None, "VPdef (mbar)": None, "sh (g/kg)": None, "H2OC (mmol/mol)": None}
    vp_max = saturation_vapor_pressure_mbar(float(temperature))
    vp_actual = vp_max * float(humidity) / 100.0
    return {
        "Tpot (K)": potential_temperature_k(float(temperature), float(pressure)),
        "Tdew (degC)": dew_point_c(float(temperature), float(humidity)),
        "VPmax (mbar)": vp_max,
        "VPact (mbar)": vp_actual,
        "VPdef (mbar)": vp_max - vp_actual,
        "sh (g/kg)": specific_humidity_gkg(float(pressure), vp_actual),
        "H2OC (mmol/mol)": 1000.0 * vp_actual / max(1.0, float(pressure) - vp_actual),
    }


def assess_fire_weather(event: dict[str, Any]) -> dict[str, Any]:
    """Apply simple screening rules and return risk details for the dashboard."""
    quality = str(event.get("data_quality", "valid")).lower()
    values = (event.get("temperature"), event.get("humidity"), event.get("wind_speed_ms"), event.get("fuel_moisture_pct"))
    if quality != "valid" or not all(is_number(value) for value in values):
        return {"status": "SENSOR_FAULT" if quality == "invalid" else "INSUFFICIENT_DATA", "severity": "critical" if quality == "invalid" else "info", "risk_score": None, "risk_level": "unknown", "is_outlier": False}
    temperature, humidity, wind, fuel = (float(value) for value in values)
    heat = min(1.0, max(0.0, (temperature - 20.0) / 22.0))
    dryness = min(1.0, max(0.0, (50.0 - humidity) / 45.0))
    wind_factor = min(1.0, max(0.0, (wind - 2.0) / 16.0))
    fuel_dryness = min(1.0, max(0.0, (22.0 - fuel) / 18.0))
    score = round(100.0 * (0.30 * heat + 0.30 * dryness + 0.20 * wind_factor + 0.20 * fuel_dryness), 1)
    if score >= 75.0:
        return {"status": "RED_FLAG_CONDITIONS", "severity": "critical", "risk_score": score, "risk_level": "extreme", "is_outlier": True}
    if score >= 50.0:
        return {"status": "HIGH_FIRE_RISK", "severity": "warning", "risk_score": score, "risk_level": "high", "is_outlier": True}
    if score >= 25.0:
        return {"status": "ELEVATED_FIRE_RISK", "severity": "advisory", "risk_score": score, "risk_level": "elevated", "is_outlier": False}
    return {"status": "NORMAL", "severity": "info", "risk_score": score, "risk_level": "low", "is_outlier": False}
