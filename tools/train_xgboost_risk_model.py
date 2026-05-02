"""Train the shipment risk XGBoost model.

This script expects a CSV with the feature columns from
app.services.shipment_risk_service.FEATURE_NAMES plus a target column named
`risk_score` in the 0-10 range.

Example:
    python tools/train_xgboost_risk_model.py --input data/shipment_training.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.shipment_risk_service import FEATURE_NAMES, MODEL_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost shipment risk model.")
    parser.add_argument("--input", required=True, help="Training CSV path.")
    parser.add_argument("--output", default=str(MODEL_PATH), help="Output model path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)

    missing = [column for column in [*FEATURE_NAMES, "risk_score"] if column not in df.columns]
    if missing:
        raise ValueError(f"Training CSV is missing required columns: {missing}")

    try:
        import joblib
        from xgboost import XGBRegressor
    except ImportError as exc:
        raise RuntimeError("Install training dependencies with: pip install xgboost joblib") from exc

    x_train = df[FEATURE_NAMES]
    y_train = df["risk_score"].clip(0, 10)

    model = XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(x_train, y_train)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output)
    print(f"Saved XGBoost risk model to {output}")


if __name__ == "__main__":
    main()
