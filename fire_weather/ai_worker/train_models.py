#!/usr/bin/env python3
"""Train and version the three prediction tasks from ML_predictions.ipynb."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "docs" / "datasets" / "jena_climate_2009_2016.csv"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "models"
DEFAULT_VERSION = "2.0.0"
RANDOM_STATE = 42
REQUIRED_COLUMNS = ("Date Time", "T (degC)", "p (mbar)", "rh (%)")
MODEL_FILES = {
    "humidity_regression": "humidity_regression_v2.pkl",
    "low_humidity_classifier": "low_humidity_classifier_v2.pkl",
    "pressure_risk_classifier": "pressure_risk_classifier_v2.pkl",
}


def load_dataset(path: Path, pressure_horizon_hours: float) -> pd.DataFrame:
    """Load, validate, and prepare the original Jena-compatible CSV."""
    frame = pd.read_csv(path)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Training CSV is missing columns: {', '.join(missing)}")
    frame = frame.loc[:, REQUIRED_COLUMNS].copy()
    frame["Date Time"] = pd.to_datetime(frame["Date Time"], dayfirst=True, errors="coerce")
    for column in ("T (degC)", "p (mbar)", "rh (%)"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna().sort_values("Date Time").drop_duplicates("Date Time").reset_index(drop=True)
    frame = frame[frame["rh (%)"].between(0, 100)]

    # Calculate the three-hour pressure rate before sampling. The old notebook
    # sampled first, which accidentally turned an 18-row shift into many days.
    typical_interval = frame["Date Time"].diff().dt.total_seconds().median()
    if not np.isfinite(typical_interval) or typical_interval <= 0:
        raise ValueError("Training timestamps do not form a usable time series.")
    horizon_rows = max(1, round(pressure_horizon_hours * 3600 / typical_interval))
    frame["previous_pressure"] = frame["p (mbar)"].shift(horizon_rows)
    frame["previous_time"] = frame["Date Time"].shift(horizon_rows)
    elapsed_hours = (frame["Date Time"] - frame["previous_time"]).dt.total_seconds() / 3600
    frame["Pressure_Rate"] = (frame["p (mbar)"] - frame["previous_pressure"]) / elapsed_hours

    for column in ("T (degC)", "p (mbar)"):
        q1, q3 = frame[column].quantile([0.25, 0.75])
        iqr = q3 - q1
        frame = frame[frame[column].between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)]
    return frame.reset_index(drop=True)


def systematic_sample(frame: pd.DataFrame, max_samples: int) -> pd.DataFrame:
    """Keep an evenly spaced sample when the source data is very large."""
    if len(frame) <= max_samples:
        return frame.copy()
    step = max(1, len(frame) // max_samples)
    return frame.iloc[::step].head(max_samples).copy().reset_index(drop=True)


def split_classification(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, ...]:
    """Create separate training, validation, and test sets for a classifier."""
    labels, counts = np.unique(y, return_counts=True)
    if len(labels) != 2 or counts.min() < 8:
        distribution = dict(zip(labels.tolist(), counts.tolist()))
        raise ValueError(f"Classification target needs both classes with at least eight rows: {distribution}")
    x_build, x_test, y_build, y_test = train_test_split(
        x, y, test_size=0.20, random_state=RANDOM_STATE, stratify=y
    )
    x_train, x_validation, y_train, y_validation = train_test_split(
        x_build, y_build, test_size=0.25, random_state=RANDOM_STATE, stratify=y_build
    )
    return x_train, x_validation, x_test, y_train, y_validation, y_test


def choose_decision_threshold(model: Any, x_validation: np.ndarray, y_validation: np.ndarray) -> float:
    """Choose the probability cutoff that gives the best validation F1 score."""
    probability = model.predict_proba(x_validation)[:, 1]
    precision, recall, thresholds = precision_recall_curve(y_validation, probability)
    if len(thresholds) == 0:
        return 0.5
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.nanargmax(f1))])


def classification_metrics(
    model: Any, x_test: np.ndarray, y_test: np.ndarray, decision_threshold: float
) -> dict[str, float]:
    """Calculate classification scores on data the model did not train on."""
    probability = model.predict_proba(x_test)[:, 1]
    predicted = (probability >= decision_threshold).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "precision": round(float(precision_score(y_test, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predicted, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, predicted, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probability)), 4),
        "decision_threshold": round(float(decision_threshold), 6),
        "positive_rate": round(float(np.mean(y_test)), 6),
    }


def save_bundle(output_dir: Path, filename: str, bundle: dict[str, Any]) -> None:
    """Save a trained model together with its version and supporting details."""
    joblib.dump(bundle, output_dir / filename)


def train_models(
    dataset: Path,
    output_dir: Path,
    model_version: str,
    max_samples: int,
    pressure_horizon_hours: float,
) -> dict[str, Any]:
    """Train all three project models and write their manifest and model files."""
    prepared = load_dataset(dataset, pressure_horizon_hours)
    sampled = systematic_sample(prepared, max_samples)
    output_dir.mkdir(parents=True, exist_ok=True)
    trained_at = datetime.now(timezone.utc).isoformat()

    features = sampled[["T (degC)", "p (mbar)"]].to_numpy()
    humidity = sampled["rh (%)"].to_numpy()
    x_train, x_test, y_train, y_test = train_test_split(
        features, humidity, test_size=0.30, random_state=RANDOM_STATE
    )
    humidity_model = Pipeline([
        ("scale", StandardScaler()),
        ("model", LinearRegression()),
    ]).fit(x_train, y_train)
    humidity_prediction = humidity_model.predict(x_test)
    humidity_metrics = {
        "r2": round(float(r2_score(y_test, humidity_prediction)), 4),
        "mae_pct": round(float(mean_absolute_error(y_test, humidity_prediction)), 4),
    }

    low_humidity = (sampled["rh (%)"] < 30).astype(int).to_numpy()
    x_train, x_validation, x_test, y_train, y_validation, y_test = split_classification(
        features, low_humidity
    )
    low_humidity_model = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
    ]).fit(x_train, y_train)
    low_humidity_threshold = choose_decision_threshold(low_humidity_model, x_validation, y_validation)
    low_humidity_metrics = classification_metrics(
        low_humidity_model, x_test, y_test, low_humidity_threshold
    )

    pressure_frame = prepared.dropna(subset=["Pressure_Rate"]).copy()
    pressure_frame["Risk_Indicator"] = (
        (pressure_frame["Pressure_Rate"] < -0.5) & (pressure_frame["T (degC)"] > 25)
    ).astype(int)
    pressure_frame = systematic_sample(pressure_frame, max_samples * 4)
    pressure_features = pressure_frame[["T (degC)", "Pressure_Rate"]].to_numpy()
    pressure_risk = pressure_frame["Risk_Indicator"].to_numpy()
    x_train, x_validation, x_test, y_train, y_validation, y_test = split_classification(
        pressure_features, pressure_risk
    )
    pressure_model = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
    ]).fit(x_train, y_train)
    pressure_threshold = choose_decision_threshold(pressure_model, x_validation, y_validation)
    pressure_metrics = classification_metrics(pressure_model, x_test, y_test, pressure_threshold)

    common = {
        "model_version": model_version,
        "trained_at": trained_at,
        "training_source": str(dataset.resolve()),
    }
    save_bundle(output_dir, MODEL_FILES["humidity_regression"], {
        **common,
        "task": "humidity_regression",
        "features": ["temperature_c", "pressure_mbar"],
        "model": humidity_model,
        "metrics": humidity_metrics,
    })
    save_bundle(output_dir, MODEL_FILES["low_humidity_classifier"], {
        **common,
        "task": "low_humidity_classifier",
        "features": ["temperature_c", "pressure_mbar"],
        "threshold": {"relative_humidity_pct": 30.0},
        "decision_threshold": low_humidity_threshold,
        "model": low_humidity_model,
        "metrics": low_humidity_metrics,
    })
    save_bundle(output_dir, MODEL_FILES["pressure_risk_classifier"], {
        **common,
        "task": "pressure_risk_classifier",
        "features": ["temperature_c", "pressure_rate_mbar_per_hour"],
        "thresholds": {"temperature_c": 25.0, "pressure_rate_mbar_per_hour": -0.5},
        "decision_threshold": pressure_threshold,
        "pressure_horizon_hours": pressure_horizon_hours,
        "model": pressure_model,
        "metrics": pressure_metrics,
    })

    manifest = {
        "schema_version": "1.0",
        "model_version": model_version,
        "trained_at": trained_at,
        "training_source": str(dataset.resolve()),
        "training_rows": int(len(prepared)),
        "sampled_rows": int(len(sampled)),
        "tasks": {
            "humidity_regression": {"file": MODEL_FILES["humidity_regression"], "metrics": humidity_metrics},
            "low_humidity_classifier": {"file": MODEL_FILES["low_humidity_classifier"], "metrics": low_humidity_metrics},
            "pressure_risk_classifier": {"file": MODEL_FILES["pressure_risk_classifier"], "metrics": pressure_metrics},
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    """Read training options, train the models, and print their results."""
    parser = argparse.ArgumentParser(description="Train the three Fire Weather prediction models.")
    parser.add_argument("--input", type=Path, default=DEFAULT_DATASET, help="Jena-compatible training CSV.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--model-version", default=DEFAULT_VERSION)
    parser.add_argument("--max-samples", type=int, default=10_000)
    parser.add_argument("--pressure-horizon-hours", type=float, default=3.0)
    args = parser.parse_args()
    if args.max_samples < 100 or args.pressure_horizon_hours <= 0:
        parser.error("max-samples must be at least 100 and pressure-horizon-hours must be positive")
    manifest = train_models(
        args.input, args.output_dir, args.model_version, args.max_samples, args.pressure_horizon_hours
    )
    print(f"[TRAINING] Complete. Model version {manifest['model_version']}")
    print(f"[TRAINING] Rows={manifest['training_rows']} sampled={manifest['sampled_rows']}")
    for task, details in manifest["tasks"].items():
        print(f"[TRAINING] {task}: {details['metrics']}")
    print(f"[TRAINING] Models saved to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
