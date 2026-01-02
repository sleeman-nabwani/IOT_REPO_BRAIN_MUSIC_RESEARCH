"""
LightGBM Training Module

Trains a LightGBM regressor to predict the next walking BPM from lag
features (one-step-ahead forecast).

Outputs:
    - results/plots/lgbm_baseline_performance.png
    - results/plots/lgbm_tuned_performance.png
    - results/models/lgbm_model.joblib
"""
import argparse
import importlib.util
import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb
except ImportError as exc:  # pragma: no cover
    raise SystemExit("LightGBM is not installed. Please run run_lgbm.bat to install dependencies.") from exc

if TYPE_CHECKING:  # pragma: no cover
    import optuna  # type: ignore

# Load the shared loader from research/analyze_data.py without clashing with this module's name.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT
RESEARCH_DIR = PROJECT_ROOT / "research"
PARENT_ANALYZE = RESEARCH_DIR / "analyze_data.py"
spec = importlib.util.spec_from_file_location("research_analyze_data", PARENT_ANALYZE)
parent_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_mod)  # type: ignore

# Load LightGBM analysis helpers from this directory without clashing names.
LGBM_ANALYZE = Path(__file__).parent / "analyze_data.py"
spec_lgbm = importlib.util.spec_from_file_location("lgbm_analyze_data", LGBM_ANALYZE)
lgbm_analyze = importlib.util.module_from_spec(spec_lgbm)
spec_lgbm.loader.exec_module(lgbm_analyze)  # type: ignore
get_raw_and_processed_sessions = lgbm_analyze.get_raw_and_processed_sessions
process_walking_data = lgbm_analyze.process_walking_data
build_lag_features = lgbm_analyze.build_lag_features

# Output directories for results
RESULTS_DIR = Path(__file__).parent / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
MODELS_DIR = RESULTS_DIR / "models"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)


WINDOW_SIZE = 4
TEST_SIZE = 0.2
RANDOM_SEED = 42
DEFAULT_OPTUNA_TRIALS = 30

BASE_PARAMS = dict(
    objective="regression",
    n_estimators=200,
    learning_rate=0.1,
    max_depth=5,
    num_leaves=31,
    subsample=0.9,
    colsample_bytree=0.9,
    min_child_samples=15,
    random_state=RANDOM_SEED,
)

TUNED_PARAMS = dict(
    objective="regression",
    n_estimators=300,
    learning_rate=0.07,
    max_depth=6,
    num_leaves=31,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_samples=10,
    random_state=RANDOM_SEED,
)


def _prepare_dataset():
    """Load, validate, and split data; returns scaled matrices and scaler."""
    logs_dir = BASE_DIR / "server" / "logs"
    raw_df, df = get_raw_and_processed_sessions(logs_dir)
    if raw_df.empty:
        print("No data found. Run some sessions first.")
        return None

    if df.empty:
        print("No valid walking_bpm values after filtering.")
        return None

    X_lag, y, meta = build_lag_features(df, window_size=WINDOW_SIZE)
    if len(X_lag) < 20:
        print(f"Not enough sequences to train (found {len(X_lag)}).")
        return None

    X = np.concatenate([X_lag, meta], axis=1) if len(meta) > 0 else X_lag
    finite_mask = np.isfinite(X).all(axis=1)
    if finite_mask.sum() < len(finite_mask):
        X = X[finite_mask]
        y = y[finite_mask]
        print(f"Dropped {len(finite_mask) - len(X)} rows with non-finite features.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    return X_train, X_test, y_train, y_test, scaler


def _plot_predictions(tag, y_true, preds, mae, r2, limit=200):
    plt.figure(figsize=(12, 5))
    plot_limit = min(limit, len(y_true))
    plt.plot(y_true[:plot_limit], label="Actual Next Step", marker="o", markersize=3)
    plt.plot(preds[:plot_limit], label="LGBM Prediction", linestyle="--", linewidth=2)
    r2_pct = r2 * 100
    plt.title(f"LGBM Prediction vs Actual - MAE: {mae:.2f} BPM, R2: {r2:.3f} ({r2_pct:.1f}%) [{tag}]")
    plt.xlabel("Step Index")
    plt.ylabel("BPM")
    plt.legend()
    plt.grid(True, alpha=0.3)
    output_path = PLOTS_DIR / f"lgbm_{tag}_performance.png"
    plt.savefig(output_path)
    print(f"Saved '{output_path}'")


def train_lgbm_model():
    prepared = _prepare_dataset()
    if prepared is None:
        return

    X_train, X_test, y_train, y_test, scaler = prepared

    def train_and_eval(params, tag):
        model = lgb.LGBMRegressor(**params)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)
        return model, preds, mae, r2, tag

    baseline_model, baseline_preds, baseline_mae, baseline_r2, baseline_tag = train_and_eval(BASE_PARAMS, "baseline")
    tuned_model, tuned_preds, tuned_mae, tuned_r2, tuned_tag = train_and_eval(TUNED_PARAMS, "tuned")

    if tuned_r2 > baseline_r2 or (abs(tuned_r2 - baseline_r2) < 1e-6 and tuned_mae <= baseline_mae):
        best_model, best_preds, best_mae, best_r2, best_tag = tuned_model, tuned_preds, tuned_mae, tuned_r2, tuned_tag
    else:
        best_model, best_preds, best_mae, best_r2, best_tag = baseline_model, baseline_preds, baseline_mae, baseline_r2, baseline_tag

    print("Comparison (same split):")
    print(f"  Baseline - MAE: {baseline_mae:.3f}, R2: {baseline_r2:.3f}")
    print(f"  Tuned    - MAE: {tuned_mae:.3f}, R2: {tuned_r2:.3f}")
    print(f"  Selected - {best_tag} (MAE: {best_mae:.3f}, R2: {best_r2:.3f})")

    _plot_predictions(baseline_tag, y_test, baseline_preds, baseline_mae, baseline_r2)
    _plot_predictions(tuned_tag, y_test, tuned_preds, tuned_mae, tuned_r2)

    artifact = {
        "model": best_model,
        "scaler": scaler,
        "window_size": WINDOW_SIZE,
        "params": {
            "selected": best_tag,
            "baseline": BASE_PARAMS,
            "tuned": TUNED_PARAMS,
        },
        "feature_schema": {
            "lags": {
                "walking": WINDOW_SIZE,
                "instant": WINDOW_SIZE,
            },
            "extra": ["smoothing_window", "stride"],
            "order": ([f"walk_lag_{i}" for i in range(WINDOW_SIZE)] +
                      [f"inst_lag_{i}" for i in range(WINDOW_SIZE)] +
                      ["smoothing_window", "stride"]),
        },
    }
    model_path = MODELS_DIR / "lgbm_model.joblib"
    joblib.dump(artifact, model_path)
    print(f"Model exported to '{model_path}'")
    if len(X_test) > 0:
        example_input = X_test[0].tolist()
        example_prediction = best_preds[0]
        print(f"Example: input {example_input} -> predicted {example_prediction:.1f} BPM")

    return best_model, model_path


def optimize_lgbm_model(trials: int = DEFAULT_OPTUNA_TRIALS, timeout: Optional[int] = None):
    try:
        import optuna  # type: ignore
    except ImportError:  # pragma: no cover
        raise SystemExit("Optuna is not installed. Re-run with run_lgbm.bat --optimize to install dependencies.")

    prepared = _prepare_dataset()
    if prepared is None:
        return

    X_train, X_test, y_train, y_test, scaler = prepared
    X_train_opt, X_val_opt, y_train_opt, y_val_opt = train_test_split(
        X_train, y_train, test_size=0.2, random_state=RANDOM_SEED
    )

    def objective(trial: optuna.Trial) -> float:
        max_depth = trial.suggest_int("max_depth", 3, 10)
        params = dict(
            objective="regression",
            boosting_type="gbdt",
            learning_rate=trial.suggest_float("learning_rate", 1e-3, 0.2, log=True),
            n_estimators=trial.suggest_int("n_estimators", 200, 800),
            max_depth=max_depth,
            num_leaves=trial.suggest_int("num_leaves", 16, min(512, 2 ** (max_depth + 1))),
            subsample=trial.suggest_float("subsample", 0.6, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.6, 1.0),
            min_child_samples=trial.suggest_int("min_child_samples", 5, 60),
            lambda_l1=trial.suggest_float("lambda_l1", 0.0, 5.0),
            lambda_l2=trial.suggest_float("lambda_l2", 0.0, 5.0),
            min_split_gain=trial.suggest_float("min_split_gain", 0.0, 1.0),
            bagging_freq=trial.suggest_int("bagging_freq", 0, 7),
            random_state=RANDOM_SEED,
            n_jobs=-1,
            verbosity=-1,
        )

        model = lgb.LGBMRegressor(**params)
        model.fit(
            X_train_opt,
            y_train_opt,
            eval_set=[(X_val_opt, y_val_opt)],
            eval_metric="rmse",
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )
        preds = model.predict(X_val_opt)
        rmse = float(np.sqrt(mean_squared_error(y_val_opt, preds)))
        return rmse

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=trials, timeout=timeout)

    print(f"Best trial: {study.best_trial.number}")
    print(f"Best RMSE: {study.best_trial.value:.4f}")
    print("Best parameters:")
    for k, v in study.best_trial.params.items():
        print(f"  {k}: {v}")

    best_params = study.best_trial.params
    best_params_full = dict(
        objective="regression",
        boosting_type="gbdt",
        n_jobs=-1,
        random_state=RANDOM_SEED,
        verbosity=-1,
        **best_params,
    )

    X_train_fit, X_val_fit, y_train_fit, y_val_fit = train_test_split(
        X_train, y_train, test_size=0.2, random_state=RANDOM_SEED
    )
    best_model = lgb.LGBMRegressor(**best_params_full)
    best_model.fit(
        X_train_fit,
        y_train_fit,
        eval_set=[(X_val_fit, y_val_fit)],
        eval_metric="rmse",
        callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
    )

    best_preds = best_model.predict(X_test)
    best_mae = mean_absolute_error(y_test, best_preds)
    best_r2 = r2_score(y_test, best_preds)
    best_rmse = float(np.sqrt(mean_squared_error(y_test, best_preds)))

    print("\nOptuna-selected model performance (held-out test):")
    print(f"  RMSE: {best_rmse:.3f}")
    print(f"  MAE : {best_mae:.3f}")
    print(f"  R2  : {best_r2:.3f}")

    _plot_predictions("tuned", y_test, best_preds, best_mae, best_r2)

    artifact = {
        "model": best_model,
        "scaler": scaler,
        "window_size": WINDOW_SIZE,
        "params": {
            "selected": "optuna",
            "optuna_best": best_params_full,
            "trials": trials,
            "best_trial": study.best_trial.number,
            "best_rmse": best_rmse,
        },
        "feature_schema": {
            "lags": {
                "walking": WINDOW_SIZE,
                "instant": WINDOW_SIZE,
            },
            "extra": ["smoothing_window", "stride"],
            "order": ([f"walk_lag_{i}" for i in range(WINDOW_SIZE)] +
                      [f"inst_lag_{i}" for i in range(WINDOW_SIZE)] +
                      ["smoothing_window", "stride"]),
        },
    }
    model_path = MODELS_DIR / "lgbm_model.joblib"
    joblib.dump(artifact, model_path)
    print(f"Model exported to '{model_path}'")

    params_path = MODELS_DIR / "lgbm_optuna_best_params.json"
    with params_path.open("w", encoding="utf-8") as fh:
        json.dump(best_params_full, fh, indent=2)
    print(f"Best parameters exported to '{params_path}'")

    if len(X_test) > 0:
        example_input = X_test[0].tolist()
        example_prediction = best_preds[0]
        print(f"Example: input {example_input} -> predicted {example_prediction:.1f} BPM")

    return best_model, model_path


def train_user_calibration(user_df, base_model_path=None, output_suffix="user_head"):
    """
    Fit a lightweight per-user linear calibration head on top of the base LightGBM predictions.

    Args:
        user_df: DataFrame containing user data with walking_bpm and session_id.
        base_model_path: Path to base LightGBM artifact (joblib). Defaults to latest lgbm_model.joblib.
        output_suffix: Identifier to distinguish the saved head artifact.

    Returns:
        calibrator (Ridge), artifact_path
    """
    if base_model_path is None:
        base_model_path = MODELS_DIR / "lgbm_model.joblib"
    if not Path(base_model_path).exists():
        raise FileNotFoundError(f"Base model not found at {base_model_path}")

    # Load base artifact
    artifact = joblib.load(base_model_path)
    base_model = artifact["model"]
    scaler = artifact["scaler"]
    window_size = artifact["window_size"]

    # Filter outliers for stability
    user_df = process_walking_data(user_df)
    if user_df.empty:
        raise ValueError("No valid user data after filtering.")

    # Build lag features
    X_lag, y, meta = build_lag_features(user_df, window_size=window_size)
    if len(X_lag) < 10:
        raise ValueError(f"Not enough user sequences to fit calibration head (found {len(X_lag)}).")
    X = np.concatenate([X_lag, meta], axis=1) if len(meta) > 0 else X_lag

    # Scale lags with the base scaler
    X_scaled = scaler.transform(X)

    # Base predictions
    base_preds = base_model.predict(X_scaled)

    # Calibration features: base prediction plus scaled lags
    calib_features = np.column_stack([base_preds, X_scaled])

    # Split for a quick validation (optional)
    X_train, X_val, y_train, y_val = train_test_split(
        calib_features, y, test_size=0.2, random_state=RANDOM_SEED
    )

    calibrator = Ridge(alpha=1.0, random_state=RANDOM_SEED)
    calibrator.fit(X_train, y_train)

    val_preds = calibrator.predict(X_val)
    val_mae = mean_absolute_error(y_val, val_preds)
    val_r2 = r2_score(y_val, val_preds)
    print("\nUser calibration head")
    print("-" * 40)
    print(f"Val MAE: {val_mae:.2f} BPM")
    print(f"Val R2 : {val_r2:.3f}")

    head_artifact = {
        "calibrator": calibrator,
        "base_model_path": str(base_model_path),
        "window_size": window_size,
        "params": {"alpha": 1.0},
    }
    head_path = MODELS_DIR / f"lgbm_user_head_{output_suffix}.joblib"
    joblib.dump(head_artifact, head_path)
    print(f"User head exported to '{head_path}'")

    return calibrator, head_path


def _parse_args():
    parser = argparse.ArgumentParser(description="Train or tune the LightGBM model.")
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Run Optuna hyperparameter search instead of fixed presets.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=DEFAULT_OPTUNA_TRIALS,
        help=f"Number of Optuna trials (default: {DEFAULT_OPTUNA_TRIALS}).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Optional Optuna timeout in seconds.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.optimize:
        optimize_lgbm_model(trials=args.trials, timeout=args.timeout)
    else:
        train_lgbm_model()

