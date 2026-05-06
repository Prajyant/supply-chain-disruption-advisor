"""Generate realistic synthetic shipment training data for XGBoost v2.

Produces diverse scenarios with non-linear feature interactions,
engineered compound features, and realistic distributions.

Example:
    python tools/generate_shipment_training_data.py
    python tools/generate_shipment_training_data.py --rows 5000 --output data/shipment_training.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.shipment_risk_service import FEATURE_NAMES, apply_context_guardrails


OUTPUT_PATH = Path("data/shipment_training.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate shipment training data.")
    parser.add_argument("--rows", type=int, default=5000, help="Number of training rows.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float]] = []

    # Scenario generators with weights
    scenarios = [
        (generate_healthy_shipment, 0.22),
        (generate_moderate_pressure, 0.15),
        (generate_weather_disruption, 0.10),
        (generate_trade_policy_shock, 0.08),
        (generate_compound_crisis, 0.08),
        (generate_high_value_urgent, 0.06),
        (generate_early_route_exposure, 0.06),
        (generate_supplier_unreliable, 0.06),
        (generate_marine_storm, 0.06),
        (generate_low_inventory_crisis, 0.05),
        (generate_multimodal_complex, 0.04),
        (generate_borderline_medium_high, 0.04),
    ]

    total_rows = args.rows
    for gen, weight in scenarios:
        count = int(total_rows * weight)
        for _ in range(count):
            rows.append(gen())

    # Fill remaining with fully random rows
    while len(rows) < total_rows:
        rows.append(generate_random_row())

    random.shuffle(rows)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*FEATURE_NAMES, "risk_score"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} training rows to {output}")

    # Print distribution stats
    scores = [r["risk_score"] for r in rows]
    levels = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for s in scores:
        if s >= 8:
            levels["critical"] += 1
        elif s >= 5:
            levels["high"] += 1
        elif s >= 3:
            levels["medium"] += 1
        else:
            levels["low"] += 1
    print(f"Distribution: {levels}")
    print(f"Mean: {sum(scores)/len(scores):.2f}, Std: {(sum((s - sum(scores)/len(scores))**2 for s in scores)/len(scores))**0.5:.2f}")


# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------

def generate_healthy_shipment() -> dict[str, float]:
    """Low-risk: short lead time, good inventory, no external signals."""
    f = {
        "lead_time_days": random.choice([3, 5, 7, 8, 10, 12]),
        "inventory_pressure": round(random.uniform(0, 3.0), 2),
        "supplier_delay_count": random.choice([0, 0, 0, 0, 1]),
        "priority_score": random.choice([0, 3.33, 3.33, 6.67]),
        "declared_value_score": round(random.uniform(0.5, 3.5), 2),
        "weather_severity_score": random.choice([0, 0, 0, 1.5]),
        "trade_severity_score": 0.0,
        "news_severity_score": random.choice([0, 0, 1.5]),
        "vessel_status_score": random.choice([0, 0, 1.5]),
        "marine_weather_score": random.choice([0, 0, 1.5]),
        "route_progress_score": random.choice([0, 2, 5]),
        "route_signal_count": random.choice([0, 0, 0, 1]),
        **random_transport_mode(),
    }
    return finalize_row(f)


def generate_moderate_pressure() -> dict[str, float]:
    """Medium risk: some inventory pressure or supplier delays."""
    f = {
        "lead_time_days": random.choice([10, 14, 18, 22]),
        "inventory_pressure": round(random.uniform(3.5, 7.0), 2),
        "supplier_delay_count": random.choice([1, 2, 2, 3]),
        "priority_score": random.choice([3.33, 6.67, 6.67]),
        "declared_value_score": round(random.uniform(2.0, 6.0), 2),
        "weather_severity_score": random.choice([0, 1.5, 4.0]),
        "trade_severity_score": random.choice([0, 0, 1.5, 4.0]),
        "news_severity_score": random.choice([0, 1.5, 4.0]),
        "vessel_status_score": random.choice([1.5, 4.0, 4.0]),
        "marine_weather_score": random.choice([0, 1.5, 4.0]),
        "route_progress_score": random.choice([2, 5, 5]),
        "route_signal_count": random.choice([1, 2, 2, 3]),
        **random_transport_mode(),
    }
    return finalize_row(f)


def generate_weather_disruption() -> dict[str, float]:
    """Weather-driven risk."""
    f = {
        "lead_time_days": random.choice([14, 18, 22, 28]),
        "inventory_pressure": round(random.uniform(3.0, 8.0), 2),
        "supplier_delay_count": random.choice([0, 1, 2]),
        "priority_score": random.choice([3.33, 6.67, 10.0]),
        "declared_value_score": round(random.uniform(2.0, 8.0), 2),
        "weather_severity_score": random.choice([7.0, 7.0, 9.0, 9.0]),
        "trade_severity_score": random.choice([0, 0, 1.5]),
        "news_severity_score": random.choice([0, 4.0, 7.0]),
        "vessel_status_score": random.choice([4.0, 7.0, 7.0]),
        "marine_weather_score": random.choice([4.0, 7.0, 9.0]),
        "route_progress_score": random.choice([5, 8, 8]),
        "route_signal_count": random.choice([2, 3, 4]),
        **random_transport_mode(bias="sea"),
    }
    return finalize_row(f)


def generate_trade_policy_shock() -> dict[str, float]:
    """Trade/geopolitical disruption."""
    f = {
        "lead_time_days": random.choice([18, 22, 28, 35]),
        "inventory_pressure": round(random.uniform(4.0, 9.0), 2),
        "supplier_delay_count": random.choice([1, 2, 3, 4]),
        "priority_score": random.choice([6.67, 6.67, 10.0]),
        "declared_value_score": round(random.uniform(3.0, 9.0), 2),
        "weather_severity_score": random.choice([0, 0, 1.5]),
        "trade_severity_score": random.choice([7.0, 7.0, 9.0, 9.0]),
        "news_severity_score": random.choice([4.0, 7.0, 9.0]),
        "vessel_status_score": random.choice([0, 1.5, 4.0]),
        "marine_weather_score": random.choice([0, 0, 1.5]),
        "route_progress_score": random.choice([0, 2, 5]),
        "route_signal_count": random.choice([2, 3, 4, 5]),
        **random_transport_mode(),
    }
    return finalize_row(f)


def generate_compound_crisis() -> dict[str, float]:
    """Multiple simultaneous signals."""
    f = {
        "lead_time_days": random.choice([22, 28, 35, 45]),
        "inventory_pressure": round(random.uniform(6.0, 10.0), 2),
        "supplier_delay_count": random.choice([3, 4, 5]),
        "priority_score": random.choice([6.67, 10.0, 10.0]),
        "declared_value_score": round(random.uniform(5.0, 10.0), 2),
        "weather_severity_score": random.choice([4.0, 7.0, 9.0]),
        "trade_severity_score": random.choice([4.0, 7.0, 9.0]),
        "news_severity_score": random.choice([4.0, 7.0, 9.0]),
        "vessel_status_score": random.choice([4.0, 7.0, 9.0]),
        "marine_weather_score": random.choice([4.0, 7.0, 9.0]),
        "route_progress_score": random.choice([5, 8, 8]),
        "route_signal_count": random.choice([4, 5, 5]),
        **random_transport_mode(bias="sea"),
    }
    return finalize_row(f)


def generate_high_value_urgent() -> dict[str, float]:
    """High-value urgent shipment."""
    f = {
        "lead_time_days": random.choice([5, 8, 10, 14]),
        "inventory_pressure": round(random.uniform(5.0, 9.0), 2),
        "supplier_delay_count": random.choice([0, 1, 2]),
        "priority_score": 10.0,
        "declared_value_score": round(random.uniform(7.0, 10.0), 2),
        "weather_severity_score": random.choice([0, 1.5, 4.0, 7.0]),
        "trade_severity_score": random.choice([0, 1.5, 4.0]),
        "news_severity_score": random.choice([0, 1.5, 4.0]),
        "vessel_status_score": random.choice([0, 1.5, 4.0, 7.0]),
        "marine_weather_score": random.choice([0, 1.5, 4.0]),
        "route_progress_score": random.choice([2, 5, 8]),
        "route_signal_count": random.choice([0, 1, 2, 3]),
        **random_transport_mode(bias="air"),
    }
    return finalize_row(f)


def generate_early_route_exposure() -> dict[str, float]:
    """Disruption early in route."""
    f = {
        "lead_time_days": random.choice([18, 22, 28, 35]),
        "inventory_pressure": round(random.uniform(3.0, 7.0), 2),
        "supplier_delay_count": random.choice([0, 1, 2]),
        "priority_score": random.choice([3.33, 6.67]),
        "declared_value_score": round(random.uniform(2.0, 7.0), 2),
        "weather_severity_score": random.choice([4.0, 7.0, 9.0]),
        "trade_severity_score": random.choice([0, 4.0, 7.0]),
        "news_severity_score": random.choice([0, 4.0]),
        "vessel_status_score": random.choice([4.0, 7.0]),
        "marine_weather_score": random.choice([4.0, 7.0, 9.0]),
        "route_progress_score": 8.0,
        "route_signal_count": random.choice([2, 3, 4]),
        **random_transport_mode(bias="sea"),
    }
    return finalize_row(f)


def generate_supplier_unreliable() -> dict[str, float]:
    """Historically unreliable supplier."""
    f = {
        "lead_time_days": random.choice([14, 18, 22, 28]),
        "inventory_pressure": round(random.uniform(4.0, 8.0), 2),
        "supplier_delay_count": random.choice([3, 4, 5, 5]),
        "priority_score": random.choice([3.33, 6.67, 6.67]),
        "declared_value_score": round(random.uniform(2.0, 6.0), 2),
        "weather_severity_score": random.choice([0, 1.5, 4.0]),
        "trade_severity_score": random.choice([0, 1.5, 4.0]),
        "news_severity_score": random.choice([0, 1.5]),
        "vessel_status_score": random.choice([1.5, 4.0, 7.0]),
        "marine_weather_score": random.choice([0, 1.5, 4.0]),
        "route_progress_score": random.choice([0, 2, 5]),
        "route_signal_count": random.choice([1, 2, 3]),
        **random_transport_mode(),
    }
    return finalize_row(f)


def generate_marine_storm() -> dict[str, float]:
    """Severe marine conditions."""
    f = {
        "lead_time_days": random.choice([14, 18, 22]),
        "inventory_pressure": round(random.uniform(3.0, 7.0), 2),
        "supplier_delay_count": random.choice([0, 1, 2]),
        "priority_score": random.choice([3.33, 6.67, 10.0]),
        "declared_value_score": round(random.uniform(3.0, 8.0), 2),
        "weather_severity_score": random.choice([4.0, 7.0, 9.0]),
        "trade_severity_score": 0.0,
        "news_severity_score": random.choice([0, 1.5, 4.0]),
        "vessel_status_score": random.choice([7.0, 9.0]),
        "marine_weather_score": random.choice([7.0, 9.0, 9.0]),
        "route_progress_score": random.choice([5, 8]),
        "route_signal_count": random.choice([2, 3, 4]),
        "is_air": 0.0,
        "is_sea": 1.0,
        "is_multimodal": 0.0,
    }
    return finalize_row(f)


def generate_low_inventory_crisis() -> dict[str, float]:
    """Critical inventory shortage with any external signal."""
    f = {
        "lead_time_days": random.choice([18, 22, 28, 35, 45]),
        "inventory_pressure": round(random.uniform(8.0, 10.0), 2),
        "supplier_delay_count": random.choice([2, 3, 4, 5]),
        "priority_score": random.choice([6.67, 10.0]),
        "declared_value_score": round(random.uniform(4.0, 10.0), 2),
        "weather_severity_score": random.choice([0, 1.5, 4.0, 7.0]),
        "trade_severity_score": random.choice([0, 1.5, 4.0]),
        "news_severity_score": random.choice([0, 1.5, 4.0, 7.0]),
        "vessel_status_score": random.choice([1.5, 4.0, 7.0]),
        "marine_weather_score": random.choice([0, 1.5, 4.0]),
        "route_progress_score": random.choice([0, 2, 5, 8]),
        "route_signal_count": random.choice([1, 2, 3, 4]),
        **random_transport_mode(),
    }
    return finalize_row(f)


def generate_multimodal_complex() -> dict[str, float]:
    """Multimodal shipment with mixed signals."""
    f = {
        "lead_time_days": random.choice([10, 14, 18, 22]),
        "inventory_pressure": round(random.uniform(3.0, 7.0), 2),
        "supplier_delay_count": random.choice([1, 2, 3]),
        "priority_score": random.choice([6.67, 10.0]),
        "declared_value_score": round(random.uniform(4.0, 9.0), 2),
        "weather_severity_score": random.choice([0, 4.0, 7.0]),
        "trade_severity_score": random.choice([0, 4.0, 7.0]),
        "news_severity_score": random.choice([0, 4.0]),
        "vessel_status_score": random.choice([0, 4.0, 7.0]),
        "marine_weather_score": random.choice([0, 4.0]),
        "route_progress_score": random.choice([2, 5, 8]),
        "route_signal_count": random.choice([1, 2, 3, 4]),
        "is_air": 0.0,
        "is_sea": 0.0,
        "is_multimodal": 1.0,
    }
    return finalize_row(f)


def generate_borderline_medium_high() -> dict[str, float]:
    """Borderline cases near the medium/high threshold (score ~4.5-5.5)."""
    f = {
        "lead_time_days": random.choice([14, 18, 22]),
        "inventory_pressure": round(random.uniform(4.5, 6.5), 2),
        "supplier_delay_count": random.choice([1, 2, 3]),
        "priority_score": random.choice([3.33, 6.67]),
        "declared_value_score": round(random.uniform(3.0, 6.0), 2),
        "weather_severity_score": random.choice([0, 1.5, 4.0, 7.0]),
        "trade_severity_score": random.choice([0, 1.5, 4.0]),
        "news_severity_score": random.choice([0, 1.5, 4.0]),
        "vessel_status_score": random.choice([1.5, 4.0, 7.0]),
        "marine_weather_score": random.choice([0, 1.5, 4.0]),
        "route_progress_score": random.choice([2, 5]),
        "route_signal_count": random.choice([1, 2, 3]),
        **random_transport_mode(),
    }
    return finalize_row(f)


def generate_random_row() -> dict[str, float]:
    """Fully random row for coverage."""
    f = {
        "lead_time_days": random.choice([3, 5, 8, 10, 14, 18, 22, 28, 35, 45]),
        "inventory_pressure": round(random.uniform(0, 10), 2),
        "supplier_delay_count": random.choice([0, 0, 1, 1, 2, 3, 4, 5]),
        "priority_score": random.choice([0, 3.33, 6.67, 10.0]),
        "declared_value_score": round(random.uniform(0.2, 10), 2),
        "weather_severity_score": random.choice([0, 0, 1.5, 4, 7, 9]),
        "trade_severity_score": random.choice([0, 0, 1.5, 4, 7, 9]),
        "news_severity_score": random.choice([0, 0, 1.5, 4, 7, 9]),
        "vessel_status_score": random.choice([0, 1.5, 1.5, 4, 7, 9]),
        "marine_weather_score": random.choice([0, 0, 1.5, 4, 7, 9]),
        "route_progress_score": random.choice([0, 2, 5, 8]),
        "route_signal_count": random.choice([0, 1, 1, 2, 3, 4, 5]),
        **random_transport_mode(),
    }
    return finalize_row(f)


# ---------------------------------------------------------------------------
# Feature engineering + labeling
# ---------------------------------------------------------------------------

def compute_engineered_features(f: dict[str, float]) -> dict[str, float]:
    """Compute the V2 engineered features from base features."""
    ext_scores = [
        f["weather_severity_score"],
        f["marine_weather_score"],
        f["trade_severity_score"],
        f["news_severity_score"],
    ]
    f["max_external_severity"] = max(ext_scores)
    f["external_signal_diversity"] = float(sum(1 for s in ext_scores if s >= 4.0))

    inv_norm = f["inventory_pressure"] / 10.0
    delay_norm = min(f["supplier_delay_count"] / 5.0, 1.0)
    f["inventory_x_delays"] = round(inv_norm * delay_norm * 10.0, 2)

    pri_norm = f["priority_score"] / 10.0
    f["urgency_pressure"] = round(pri_norm * inv_norm * 10.0, 2)

    marine_norm = f["marine_weather_score"] / 10.0
    vessel_norm = f["vessel_status_score"] / 10.0
    f["marine_compound"] = round(marine_norm * vessel_norm * 10.0, 2) if marine_norm > 0 and vessel_norm > 0 else 0.0

    trade_norm = f["trade_severity_score"] / 10.0
    news_norm = f["news_severity_score"] / 10.0
    f["geopolitical_compound"] = round(trade_norm * news_norm * 10.0, 2) if trade_norm > 0 and news_norm > 0 else 0.0

    f["early_route_exposure"] = round(
        (f["route_progress_score"] / 10.0) * (f["max_external_severity"] / 10.0) * 10.0, 2
    )

    f["core_pressure"] = round(
        min(f["lead_time_days"] / 45.0, 1.0) * 1.0
        + inv_norm * 2.2
        + delay_norm * 1.2
        + pri_norm * 1.0
        + min(f["declared_value_score"] / 10.0, 1.0) * 0.5
        + vessel_norm * 1.2,
        2,
    )

    return f


def compute_label(f: dict[str, float]) -> float:
    """Expert-rule label with non-linear interactions and diminishing returns."""
    score = 0.0

    # Base features with diminishing returns
    score += _dim(f["lead_time_days"] / 45.0) * 1.0
    score += _dim(f["inventory_pressure"] / 10.0) * 2.3
    score += _dim(f["supplier_delay_count"] / 5.0) * 1.3
    score += _dim(f["priority_score"] / 10.0) * 0.9
    score += _dim(f["declared_value_score"] / 10.0) * 0.5

    # External signals
    score += _dim(f["weather_severity_score"] / 10.0) * 0.8
    score += _dim(f["trade_severity_score"] / 10.0) * 1.1
    score += _dim(f["news_severity_score"] / 10.0) * 0.5
    score += _dim(f["vessel_status_score"] / 10.0) * 1.2
    score += _dim(f["marine_weather_score"] / 10.0) * 0.8
    score += _dim(f["route_progress_score"] / 10.0) * 0.5
    score += _dim(f["route_signal_count"] / 5.0) * 0.7

    # Engineered interaction features (model learns these directly)
    score += _dim(f["inventory_x_delays"] / 10.0) * 0.8
    score += _dim(f["urgency_pressure"] / 10.0) * 0.6
    score += _dim(f["marine_compound"] / 10.0) * 0.7
    score += _dim(f["geopolitical_compound"] / 10.0) * 0.5
    score += _dim(f["early_route_exposure"] / 10.0) * 0.4

    # Signal diversity bonus (systemic risk)
    diversity = f["external_signal_diversity"]
    if diversity >= 3:
        score += 0.5 * (diversity - 2)
    elif diversity >= 2:
        score += 0.2

    # Core pressure gates external amplification
    core = f["core_pressure"]
    max_ext = f["max_external_severity"]
    if core >= 4.0 and max_ext >= 7.0:
        score += 0.6
    elif core >= 3.0 and max_ext >= 7.0 and diversity >= 2:
        score += 0.4

    # Transport mode
    if f["is_air"]:
        score += 0.2
    if f["is_multimodal"]:
        score += 0.4
    if f["is_sea"] and f["marine_compound"] >= 4.0:
        score += 0.3

    # Apply guardrails
    score = apply_context_guardrails(f, score)

    # Realistic noise
    noise = random.gauss(0, 0.12)
    return max(0.0, min(10.0, round(score + noise, 2)))


def finalize_row(f: dict[str, float]) -> dict[str, float]:
    """Compute engineered features and label, return complete row."""
    f = compute_engineered_features(f)
    score = compute_label(f)
    return {**f, "risk_score": score}


def _dim(x: float) -> float:
    """Diminishing returns: sqrt-based scaling capped at 1.0."""
    return min(1.0, math.sqrt(max(0.0, x)))


def random_transport_mode(bias: str | None = None) -> dict[str, float]:
    """Generate transport mode features."""
    if bias == "sea":
        mode = random.choices(["sea", "air", "multimodal"], weights=[0.8, 0.05, 0.15])[0]
    elif bias == "air":
        mode = random.choices(["sea", "air", "multimodal"], weights=[0.2, 0.6, 0.2])[0]
    else:
        mode = random.choices(["sea", "air", "multimodal"], weights=[0.6, 0.2, 0.2])[0]

    return {
        "is_air": 1.0 if mode == "air" else 0.0,
        "is_sea": 1.0 if mode == "sea" else 0.0,
        "is_multimodal": 1.0 if mode == "multimodal" else 0.0,
    }


if __name__ == "__main__":
    main()
