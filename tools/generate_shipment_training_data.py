"""Generate deterministic synthetic shipment training data for XGBoost."""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.shipment_risk_service import FEATURE_NAMES, apply_context_guardrails


OUTPUT_PATH = Path("data/shipment_training.csv")


def main() -> None:
    random.seed(42)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = [make_row(index) for index in range(360)]
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*FEATURE_NAMES, "risk_score"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} training rows to {OUTPUT_PATH}")


def make_row(index: int) -> dict[str, float]:
    lead_time_days = random.choice([5, 8, 10, 14, 18, 22, 28, 35, 45])
    inventory_pressure = round(random.uniform(0, 10), 2)
    supplier_delay_count = random.choice([0, 0, 1, 1, 2, 3, 4, 5])
    priority_score = random.choice([0, 3.33, 6.67, 10.0])
    declared_value_score = round(random.uniform(0.2, 10), 2)
    weather_severity_score = random.choice([0, 0, 1.5, 4, 7, 9])
    trade_severity_score = random.choice([0, 0, 1.5, 4, 7, 9])
    news_severity_score = random.choice([0, 0, 1.5, 4, 7, 9])
    vessel_status_score = random.choice([0, 1.5, 1.5, 4, 7, 9])
    marine_weather_score = random.choice([0, 0, 1.5, 4, 7, 9])
    route_progress_score = random.choice([0, 2, 5, 8])
    route_signal_count = random.choice([0, 1, 1, 2, 3, 4, 5])
    mode = random.choice(["sea", "sea", "sea", "air", "multimodal"])
    is_air = 1.0 if mode == "air" else 0.0
    is_sea = 1.0 if mode == "sea" else 0.0
    is_multimodal = 1.0 if mode == "multimodal" else 0.0

    score = synthetic_label(
        lead_time_days=lead_time_days,
        inventory_pressure=inventory_pressure,
        supplier_delay_count=supplier_delay_count,
        priority_score=priority_score,
        declared_value_score=declared_value_score,
        weather_severity_score=weather_severity_score,
        trade_severity_score=trade_severity_score,
        news_severity_score=news_severity_score,
        vessel_status_score=vessel_status_score,
        marine_weather_score=marine_weather_score,
        route_progress_score=route_progress_score,
        route_signal_count=route_signal_count,
        is_air=is_air,
        is_sea=is_sea,
        is_multimodal=is_multimodal,
    )

    # Add a little deterministic noise so the model does not learn a perfectly rigid rule.
    score = max(0.0, min(10.0, score + random.uniform(-0.35, 0.35)))

    return {
        "lead_time_days": lead_time_days,
        "inventory_pressure": inventory_pressure,
        "supplier_delay_count": supplier_delay_count,
        "priority_score": priority_score,
        "declared_value_score": declared_value_score,
        "weather_severity_score": weather_severity_score,
        "trade_severity_score": trade_severity_score,
        "news_severity_score": news_severity_score,
        "vessel_status_score": vessel_status_score,
        "marine_weather_score": marine_weather_score,
        "route_progress_score": route_progress_score,
        "route_signal_count": route_signal_count,
        "is_air": is_air,
        "is_sea": is_sea,
        "is_multimodal": is_multimodal,
        "risk_score": round(score, 2),
    }


def synthetic_label(**features: float) -> float:
    """Expert-rule label used only for demo training."""
    score = 0.0
    score += min(features["lead_time_days"] / 45.0, 1.0) * 0.9
    score += min(features["inventory_pressure"] / 10.0, 1.0) * 2.0
    score += min(features["supplier_delay_count"] / 5.0, 1.0) * 1.0
    score += min(features["priority_score"] / 10.0, 1.0) * 0.9
    score += min(features["declared_value_score"] / 10.0, 1.0) * 0.5
    score += min(features["weather_severity_score"] / 10.0, 1.0) * 0.8
    score += min(features["trade_severity_score"] / 10.0, 1.0) * 1.1
    score += min(features["news_severity_score"] / 10.0, 1.0) * 0.5
    score += min(features["vessel_status_score"] / 10.0, 1.0) * 1.2
    score += min(features["marine_weather_score"] / 10.0, 1.0) * 0.8
    score += min(features["route_progress_score"] / 10.0, 1.0) * 0.4
    score += min(features["route_signal_count"] / 5.0, 1.0) * 0.7

    if features["inventory_pressure"] >= 8 and features["priority_score"] >= 6.67:
        score += 0.7
    if features["marine_weather_score"] >= 7 and features["vessel_status_score"] >= 7:
        score += 0.5
    if features["trade_severity_score"] >= 7 and features["news_severity_score"] >= 7:
        score += 0.4
    if features["is_air"]:
        score += 0.2
    if features["is_multimodal"]:
        score += 0.4

    return apply_context_guardrails(features, score)


if __name__ == "__main__":
    main()
