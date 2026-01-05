"""
LightGBM tuning module

Performs a small grid search over window sizes and LightGBM hyperparameters,
using the same cleaning as train_lgbm (true steps only, spike removal).
Saves the best model and a performance plot.
"""
import importlib.util
from itertools import product
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb
except ImportError as exc:
    raise SystemExit("LightGBM is not installed. Please run run_lgbm.bat to install dependencies.") from exc

# Load shared loader
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT
RESEARCH_DIR = PROJECT_ROOT / "research"

# Load LightGBM analysis helpers from this directory without clashing names.
LGBM_ANALYZE = Path(__file__).parent / "analyze_data.py"
spec_lgbm = importlib.util.spec_from_file_location("lgbm_analyze_data", LGBM_ANALYZE)
lgbm_analyze = importlib.util.module_from_spec(spec_lgbm)
spec_lgbm.loader.exec_module(lgbm_analyze)  # type: ignore
get_raw_and_processed_sessions = lgbm_analyze.get_raw_and_processed_sessions
build_lag_features = lgbm_analyze.build_lag_features

# Paths
RESULTS_DIR = Path(__file__).parent / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
MODELS_DIR = RESULTS_DIR / "models"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Fixed params
TEST_SIZE = 0.2
RANDOM_SEED = 42


def tune_lgbm():
    logs_dir = BASE_DIR / "server" / "logs"
    raw_df, df = get_raw_and_processed_sessions(logs_dir)
    if raw_df.empty:
        print("No data found.")
        return

    if df.empty:
        print("No valid walking_bpm values after filtering.")
        return

    window_grid = [3, 4, 5, 6, 7, 8]
    param_grid = {
        "max_depth": [4, 6],
        "num_leaves": [15, 31],
        "learning_rate": [0.05, 0.07],
        "n_estimators": [200, 400],
    }

    best = {"mae": float("inf")}

    for w in window_grid:
        X_lag, y, meta, mode_mapping = build_lag_features(df, window_size=w)
        if len(X_lag) < 20:
            continue
        X = np.concatenate([X_lag, meta], axis=1) if len(meta) > 0 else X_lag
        finite_mask = np.isfinite(X).all(axis=1)
        if finite_mask.sum() < len(finite_mask):
            X = X[finite_mask]
            y = y[finite_mask]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED
        )
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        for md, nl, lr, ne in product(
            param_grid["max_depth"],
            param_grid["num_leaves"],
            param_grid["learning_rate"],
            param_grid["n_estimators"],
        ):
            model = lgb.LGBMRegressor(
                objective="regression",
                max_depth=md,
                num_leaves=nl,
                learning_rate=lr,
                n_estimators=ne,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_samples=10,
                random_state=RANDOM_SEED,
            )
            model.fit(X_train_s, y_train)
            preds = model.predict(X_test_s)
            mae = mean_absolute_error(y_test, preds)
            r2 = r2_score(y_test, preds)

            if mae < best["mae"]:
                best.update(
                    {
                        "mae": mae,
                        "r2": r2,
                        "model": model,
                        "scaler": scaler,
                        "window_size": w,
                        "params": {
                            "max_depth": md,
                            "num_leaves": nl,
                            "learning_rate": lr,
                            "n_estimators": ne,
                        },
                        "mode_mapping": mode_mapping,
                        "y_test": y_test,
                        "preds": preds,
                    }
                )
                print(
                    f"New best: window={w}, md={md}, nl={nl}, lr={lr}, ne={ne}, "
                    f"MAE={mae:.2f}, R2={r2:.3f}"
                )

    if best["mae"] == float("inf"):
        print("No viable configuration found.")
        return

    # Plot
    plt.figure(figsize=(12, 5))
    limit = min(200, len(best["y_test"]))
    plt.plot(best["y_test"][:limit], label="Actual Next Step", marker="o", markersize=3)
    plt.plot(best["preds"][:limit], label="LGBM Prediction", linestyle="--", linewidth=2)
    plt.title(
        f'LGBM Prediction vs Actual - MAE: {best["mae"]:.2f} BPM, R2: {best["r2"]:.3f}'
    )
    plt.xlabel("Step Index")
    plt.ylabel("BPM")
    plt.legend()
    plt.grid(True, alpha=0.3)
    output_path = PLOTS_DIR / "lgbm_tuned_performance.png"
    plt.savefig(output_path)
    print(f"Saved '{output_path}'")

    # Save
    artifact = {
        "model": best["model"],
        "scaler": best["scaler"],
        "window_size": best["window_size"],
        "params": best["params"],
        "feature_schema": {
            "lags": {
                "walking": best["window_size"],
                "instant": best["window_size"],
            },
            "extra": ["smoothing_window", "stride", "mode"],
            "mode_mapping": best.get("mode_mapping", {"unknown": 0.0}),
            "order": ([f"walk_lag_{i}" for i in range(best["window_size"])] +
                      [f"inst_lag_{i}" for i in range(best["window_size"])] +
                      ["smoothing_window", "stride", "mode"]),
        },
    }
    model_path = MODELS_DIR / "lgbm_model.joblib"
    joblib.dump(artifact, model_path)
    print(f"Model exported to '{model_path}'")


if __name__ == "__main__":
    tune_lgbm()

