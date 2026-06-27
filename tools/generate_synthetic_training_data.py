"""Generate SYNTHETIC shipment risk training data for pipeline validation.

IMPORTANT / HONEST DISCLAIMER
-----------------------------
This data is SYNTHETIC. It exists to validate the XGBoost training pipeline
end-to-end, NOT to claim real predictive performance on real disruptions.

The labels come from a hand-crafted "ground-truth" function that is
DELIBERATELY DIFFERENT from app.services.shipment_risk_service.heuristic_risk_score:

  * The heuristic is a LINEAR weighted sum with per-feature saturation and
    post-hoc guardrails.
  * The ground-truth here uses MULTIPLICATIVE interactions, THRESHOLD/regime
    effects, and a LOGISTIC squashing function, then adds Gaussian noise to
    simulate real-world messiness.

Because the signal is nonlinear and noisy, XGBoost has to learn something the
simple heuristic cannot reproduce. Expect believable metrics (R^2 ~ 0.8-0.9),
not a suspicious ~0.99. In production this would be retrained on real shipment
outcomes.

Output: a CSV with all FEATURE_NAMES columns + a `risk_score` target (0-10).

Example:
    python tools/generate_synthetic_training_data.py --rows 3000 --output data/shipment_training.csv
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.shipment_risk_service import FEATURE_NAMES

# Discrete external-severity levels used by the real feature extractor
# (SEVERITY_SCORE values). 0.0 means "no matching event of that type".
SEVERITY_LEVELS = np.array([0.0, 1.5, 4.0, 7.0, 9.0])
SEVERITY_PROBS = np.array([0.45, 0.15, 0.20, 0.13, 0.07])  # most shipments have no/low signal

ROUTE_PROGRESS_LEVELS = np.array([0.0, 2.0, 5.0, 8.0])
ROUTE_PROGRESS_PROBS = np.array([0.30, 0.25, 0.25, 0.20])


def sample_base_features(rng: np.random.Generator, n: int) -> pd.DataFrame:
    """Sample the 15 raw/base features across realistic domains."""
    # Continuous operational features
    lead_time_days = np.clip(rng.gamma(shape=2.2, scale=12.0, size=n), 0, 120).round(1)
    inventory_pressure = np.clip(rng.beta(2.0, 2.5, size=n) * 10.0, 0, 10).round(2)
    supplier_delay_count = rng.poisson(1.4, size=n).astype(float)
    supplier_delay_count = np.clip(supplier_delay_count, 0, 12)

    # Priority maps to the buyer scale 0/normal/high/urgent -> 0-10 buckets
    priority_score = rng.choice([1.0, 3.0, 6.0, 8.0, 10.0], size=n, p=[0.15, 0.4, 0.25, 0.15, 0.05])

    # Declared value 0-10 exposure
    declared_value_score = np.clip(rng.beta(1.6, 3.0, size=n) * 10.0, 0, 10).round(2)

    # External severity signals (discrete, often absent)
    weather = rng.choice(SEVERITY_LEVELS, size=n, p=SEVERITY_PROBS)
    trade = rng.choice(SEVERITY_LEVELS, size=n, p=SEVERITY_PROBS)
    news = rng.choice(SEVERITY_LEVELS, size=n, p=SEVERITY_PROBS)
    vessel = rng.choice(SEVERITY_LEVELS, size=n, p=SEVERITY_PROBS)
    marine = rng.choice(SEVERITY_LEVELS, size=n, p=SEVERITY_PROBS)

    route_progress = rng.choice(ROUTE_PROGRESS_LEVELS, size=n, p=ROUTE_PROGRESS_PROBS)

    # route_signal_count correlates with how many external signals are present
    present = (
        (weather > 0).astype(int)
        + (trade > 0).astype(int)
        + (news > 0).astype(int)
        + (vessel > 0).astype(int)
        + (marine > 0).astype(int)
    )
    noise = rng.integers(0, 2, size=n)
    route_signal_count = np.clip(present + noise - rng.integers(0, 2, size=n), 0, 5).astype(float)

    # Transport mode one-hot (sea-heavy supply chain)
    mode = rng.choice(["sea", "air", "multimodal"], size=n, p=[0.6, 0.25, 0.15])
    is_air = (mode == "air").astype(float)
    is_sea = (mode == "sea").astype(float)
    is_multimodal = (mode == "multimodal").astype(float)

    # Vessel/marine signals only meaningful for sea shipments
    vessel = np.where(is_sea == 1.0, vessel, 0.0)
    marine = np.where(is_sea == 1.0, marine, 0.0)

    return pd.DataFrame(
        {
            "lead_time_days": lead_time_days,
            "inventory_pressure": inventory_pressure,
            "supplier_delay_count": supplier_delay_count,
            "priority_score": priority_score,
            "declared_value_score": declared_value_score,
            "weather_severity_score": weather,
            "trade_severity_score": trade,
            "news_severity_score": news,
            "vessel_status_score": vessel,
            "marine_weather_score": marine,
            "route_progress_score": route_progress,
            "route_signal_count": route_signal_count,
            "is_air": is_air,
            "is_sea": is_sea,
            "is_multimodal": is_multimodal,
        }
    )


def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the 8 V2 engineered features EXACTLY as the service does."""
    weather = df["weather_severity_score"]
    marine = df["marine_weather_score"]
    trade = df["trade_severity_score"]
    news = df["news_severity_score"]
    vessel = df["vessel_status_score"]
    progress = df["route_progress_score"]

    ext = np.vstack([weather, marine, trade, news])
    df["max_external_severity"] = ext.max(axis=0)
    df["external_signal_diversity"] = (ext >= 4.0).sum(axis=0).astype(float)

    inv_norm = df["inventory_pressure"] / 10.0
    delay_norm = np.minimum(df["supplier_delay_count"] / 5.0, 1.0)
    pri_norm = df["priority_score"] / 10.0

    df["inventory_x_delays"] = (inv_norm * delay_norm * 10.0).round(2)
    df["urgency_pressure"] = (pri_norm * inv_norm * 10.0).round(2)

    df["marine_compound"] = np.where(
        (marine > 0) & (vessel > 0),
        ((marine / 10.0) * (vessel / 10.0) * 10.0).round(2),
        0.0,
    )
    df["geopolitical_compound"] = np.where(
        (trade > 0) & (news > 0),
        ((trade / 10.0) * (news / 10.0) * 10.0).round(2),
        0.0,
    )
    df["early_route_exposure"] = (
        (progress / 10.0) * (df["max_external_severity"] / 10.0) * 10.0
    ).round(2)

    df["core_pressure"] = (
        np.minimum(df["lead_time_days"] / 45.0, 1.0) * 1.0
        + inv_norm * 2.2
        + delay_norm * 1.2
        + pri_norm * 1.0
        + np.minimum(df["declared_value_score"] / 10.0, 1.0) * 0.5
        + np.minimum(vessel / 10.0, 1.0) * 1.2
    ).round(2)

    return df


def ground_truth_risk(df: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Hidden ground-truth label function: nonlinear, with regimes + noise.

    Deliberately NOT the linear heuristic. Uses multiplicative interactions,
    threshold regimes, and a logistic squash so XGBoost must learn a genuine
    nonlinear signal rather than reproduce a weighted sum.
    """
    n = len(df)

    # Normalized drivers (different normalizers than the heuristic on purpose)
    lead = np.minimum(df["lead_time_days"] / 60.0, 1.0)
    inv = df["inventory_pressure"] / 10.0
    delay = np.minimum(df["supplier_delay_count"] / 8.0, 1.0)
    pri = df["priority_score"] / 10.0
    val = df["declared_value_score"] / 10.0
    weather = df["weather_severity_score"] / 10.0
    marine = df["marine_weather_score"] / 10.0
    trade = df["trade_severity_score"] / 10.0
    news = df["news_severity_score"] / 10.0
    vessel = df["vessel_status_score"] / 10.0
    progress = df["route_progress_score"] / 10.0
    signals = df["route_signal_count"] / 5.0

    max_ext = np.maximum.reduce([weather, marine, trade, news])

    # --- Linear-ish contributions ---
    z = (
        2.6 * inv
        + 2.0 * delay
        + 1.1 * pri
        + 0.9 * lead
        + 0.5 * val
        + 1.7 * vessel
        + 1.2 * np.maximum(weather, marine)
        + 0.9 * trade
        + 0.6 * news
        + 0.7 * signals
    )

    # --- Multiplicative INTERACTIONS (the heuristic cannot represent these) ---
    z += 3.2 * (inv * delay)                 # low buffer AND late supplier compounds hard
    z += 2.0 * (progress * max_ext)          # early-route shipment hit by external shock
    z += 1.8 * (trade * news)                # geopolitical compound
    z += 1.4 * (marine * vessel)             # marine weather on a struggling vessel
    z += 1.3 * (pri * inv)                    # urgent order with thin inventory

    # --- THRESHOLD / regime effects (nonlinear kinks) ---
    z += np.where((inv > 0.8) & (delay > 0.5), 1.6, 0.0)      # acute supply squeeze
    z += np.where(max_ext >= 0.7, 0.9, 0.0)                    # any severe external event
    z -= np.where((inv < 0.3) & (delay < 0.2) & (max_ext < 0.4), 1.4, 0.0)  # healthy shipment

    # --- Mode effects ---
    z += df["is_multimodal"] * 0.5
    z -= df["is_air"] * 0.3

    # Logistic squash into 0-10 (calibrated center/spread for a full spread)
    center, spread = 6.0, 2.6
    score = 10.0 / (1.0 + np.exp(-(z - center) / spread))

    # Real-world messiness: heteroscedastic Gaussian noise (more noise mid-range)
    noise_sd = 0.55 + 0.45 * (1.0 - np.abs(score - 5.0) / 5.0)
    score = score + rng.normal(0.0, noise_sd, size=n)

    return np.clip(score, 0.0, 10.0).round(3)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic shipment risk training data.")
    parser.add_argument("--rows", type=int, default=3000, help="Number of synthetic shipments.")
    parser.add_argument("--output", default="data/shipment_training.csv", help="Output CSV path.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    df = sample_base_features(rng, args.rows)
    df = add_engineered_features(df)
    df["risk_score"] = ground_truth_risk(df, rng)

    # Ensure exact column order: all features then target
    ordered = df[[*FEATURE_NAMES, "risk_score"]]

    missing = [c for c in [*FEATURE_NAMES, "risk_score"] if c not in ordered.columns]
    if missing:
        raise RuntimeError(f"Generated frame missing columns: {missing}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_csv(output, index=False)

    y = ordered["risk_score"]
    print(f"[OK] Wrote {len(ordered)} synthetic rows -> {output}")
    print(f"     SYNTHETIC DATA — for pipeline validation only, not real outcomes.")
    print(f"     Target: min={y.min():.2f} max={y.max():.2f} mean={y.mean():.2f} std={y.std():.2f}")
    for name, (lo, hi) in [("low", (0, 3)), ("medium", (3, 5)), ("high", (5, 8)), ("critical", (8, 10.01))]:
        pct = 100.0 * ((y >= lo) & (y < hi)).mean()
        print(f"       {name:9s}: {pct:5.1f}%")


if __name__ == "__main__":
    main()
