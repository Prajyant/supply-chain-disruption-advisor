"""Train the shipment risk XGBoost model with cross-validation.

This script expects a CSV with the feature columns from
app.services.shipment_risk_service.FEATURE_NAMES plus a target column named
`risk_score` in the 0-10 range.

Features:
- 5-fold cross-validation with metrics reporting
- Hyperparameter search (random search, 40 trials)
- Feature importance output
- Train/test split evaluation
- Model versioning with metadata

Example:
    python tools/train_xgboost_risk_model.py --input data/shipment_training.csv
    python tools/train_xgboost_risk_model.py --input data/shipment_training.csv --tune
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.shipment_risk_service import FEATURE_NAMES, MODEL_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost shipment risk model.")
    parser.add_argument("--input", required=True, help="Training CSV path.")
    parser.add_argument("--output", default=str(MODEL_PATH), help="Output model path.")
    parser.add_argument("--tune", action="store_true", help="Run hyperparameter search.")
    parser.add_argument("--folds", type=int, default=5, help="Cross-validation folds.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split ratio.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)

    missing = [col for col in [*FEATURE_NAMES, "risk_score"] if col not in df.columns]
    if missing:
        raise ValueError(f"Training CSV is missing required columns: {missing}")

    try:
        import joblib
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        from sklearn.model_selection import KFold, cross_val_score, train_test_split
        from xgboost import XGBRegressor
    except ImportError as exc:
        raise RuntimeError(
            "Install training dependencies: pip install xgboost joblib scikit-learn numpy"
        ) from exc

    X = df[FEATURE_NAMES].values
    y = df["risk_score"].clip(0, 10).values

    print(f"\n{'='*60}")
    print(f"SHIPMENT RISK MODEL TRAINING (v2 - {len(FEATURE_NAMES)} features)")
    print(f"{'='*60}")
    print(f"Dataset: {args.input} ({len(df)} rows)")
    print(f"Features: {len(FEATURE_NAMES)}")
    print(f"Target: [{y.min():.2f}, {y.max():.2f}], mean={y.mean():.2f}, std={y.std():.2f}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=42
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # Hyperparameter selection
    if args.tune:
        print(f"\n--- Hyperparameter Search (40 trials, {args.folds}-fold CV) ---")
        best_params = hyperparameter_search(X_train, y_train, n_folds=args.folds)
    else:
        best_params = {
            "n_estimators": 500,
            "max_depth": 6,
            "learning_rate": 0.04,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "gamma": 0.05,
            "reg_alpha": 0.05,
            "reg_lambda": 1.5,
        }

    # Train final model
    model = XGBRegressor(
        **best_params,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # Cross-validation
    print(f"\n--- {args.folds}-Fold Cross-Validation ---")
    kf = KFold(n_splits=args.folds, shuffle=True, random_state=42)
    cv_mae_scores = cross_val_score(model, X_train, y_train, cv=kf, scoring="neg_mean_absolute_error")
    cv_mae = -cv_mae_scores.mean()
    cv_mae_std = cv_mae_scores.std()
    cv_r2_scores = cross_val_score(model, X_train, y_train, cv=kf, scoring="r2")
    cv_r2 = cv_r2_scores.mean()
    print(f"CV MAE: {cv_mae:.4f} +/- {cv_mae_std:.4f}")
    print(f"CV R2:  {cv_r2:.4f} +/- {cv_r2_scores.std():.4f}")

    # Test set evaluation
    print(f"\n--- Test Set Evaluation ---")
    y_pred = np.clip(model.predict(X_test), 0, 10)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R2:   {r2:.4f}")

    level_acc = compute_level_accuracy(y_test, y_pred)
    within_one = compute_within_one_level(y_test, y_pred)
    print(f"Level Accuracy: {level_acc:.1f}%")
    print(f"Within +/-1 Level: {within_one:.1f}%")

    # Per-level accuracy breakdown
    print(f"\n--- Per-Level Accuracy ---")
    for level_name, (lo, hi) in [("low", (0, 3)), ("medium", (3, 5)), ("high", (5, 8)), ("critical", (8, 10.01))]:
        mask = (y_test >= lo) & (y_test < hi)
        if mask.sum() > 0:
            level_pred = y_pred[mask]
            level_true = y_test[mask]
            level_mae = mean_absolute_error(level_true, level_pred)
            level_correct = sum(1 for t, p in zip(level_true, level_pred) if score_to_level(t) == score_to_level(p))
            level_pct = 100.0 * level_correct / mask.sum()
            print(f"  {level_name:10s}: n={mask.sum():4d}, MAE={level_mae:.3f}, accuracy={level_pct:.1f}%")

    # Feature importance
    print(f"\n--- Feature Importance (top 12) ---")
    importances = dict(zip(FEATURE_NAMES, model.feature_importances_))
    sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    for name, imp in sorted_imp[:12]:
        bar = "#" * int(imp * 40)
        print(f"  {name:28s} {imp:.4f} {bar}")

    # Save model
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output)
    print(f"\n[OK] Saved model to {output}")

    # Save metadata
    metadata = {
        "model_version": "shipment-risk-v2",
        "training_rows": len(df),
        "feature_count": len(FEATURE_NAMES),
        "features": FEATURE_NAMES,
        "hyperparameters": best_params,
        "metrics": {
            "cv_mae": round(cv_mae, 4),
            "cv_r2": round(float(cv_r2), 4),
            "test_mae": round(mae, 4),
            "test_rmse": round(rmse, 4),
            "test_r2": round(r2, 4),
            "level_accuracy_pct": round(level_acc, 1),
            "within_one_level_pct": round(within_one, 1),
        },
        "feature_importance": {name: round(float(imp), 4) for name, imp in sorted_imp},
    }
    meta_path = output.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(metadata, indent=2))
    print(f"[OK] Saved metadata to {meta_path}")
    print(f"\n{'='*60}")


def hyperparameter_search(
    X_train: np.ndarray, y_train: np.ndarray, n_folds: int = 5
) -> dict:
    """Random search over hyperparameter space (40 trials)."""
    from sklearn.model_selection import KFold, cross_val_score
    from xgboost import XGBRegressor
    import random

    random.seed(42)

    param_space = {
        "n_estimators": [200, 300, 400, 500, 600, 800],
        "max_depth": [4, 5, 6, 7, 8],
        "learning_rate": [0.01, 0.02, 0.03, 0.04, 0.05, 0.08],
        "subsample": [0.7, 0.75, 0.8, 0.85, 0.9],
        "colsample_bytree": [0.7, 0.75, 0.8, 0.85, 0.9],
        "min_child_weight": [1, 2, 3, 5, 7],
        "gamma": [0, 0.01, 0.05, 0.1, 0.2],
        "reg_alpha": [0, 0.01, 0.05, 0.1, 0.5],
        "reg_lambda": [0.5, 1.0, 1.5, 2.0, 3.0],
    }

    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
    best_score = float("inf")
    best_params = {}
    n_trials = 40

    for trial in range(n_trials):
        params = {key: random.choice(values) for key, values in param_space.items()}
        model = XGBRegressor(
            **params,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1,
        )
        scores = cross_val_score(model, X_train, y_train, cv=kf, scoring="neg_mean_absolute_error")
        mae = -scores.mean()

        marker = " <- best" if mae < best_score else ""
        if mae < best_score:
            best_score = mae
            best_params = params
        print(f"  [{trial+1:2d}/{n_trials}] MAE={mae:.4f}{marker}")

    print(f"\n  Best CV MAE: {best_score:.4f}")
    print(f"  Best params: {best_params}")
    return best_params


def score_to_level(score: float) -> int:
    """Convert 0-10 score to level index."""
    if score >= 8:
        return 3
    if score >= 5:
        return 2
    if score >= 3:
        return 1
    return 0


def compute_level_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Percentage of predictions where the risk level matches exactly."""
    true_levels = [score_to_level(s) for s in y_true]
    pred_levels = [score_to_level(s) for s in y_pred]
    correct = sum(1 for t, p in zip(true_levels, pred_levels) if t == p)
    return 100.0 * correct / len(true_levels)


def compute_within_one_level(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Percentage of predictions within +/-1 risk level."""
    true_levels = [score_to_level(s) for s in y_true]
    pred_levels = [score_to_level(s) for s in y_pred]
    within = sum(1 for t, p in zip(true_levels, pred_levels) if abs(t - p) <= 1)
    return 100.0 * within / len(true_levels)


if __name__ == "__main__":
    main()
