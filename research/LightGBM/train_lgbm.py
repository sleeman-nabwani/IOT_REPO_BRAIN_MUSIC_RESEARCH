"""
LightGBM Training Module

Trains a LightGBM regressor to predict the next walking BPM from lag
features (one-step-ahead forecast).

Outputs:
    - results/plots/lgbm_performance.png
    - results/models/lgbm_model.joblib
"""
import importlib.util
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

try:
    import lightgbm as lgb
except ImportError as exc:  # pragma: no cover
    raise SystemExit("LightGBM is not installed. Please run run_lgbm.bat to install dependencies.") from exc

# Load the shared loader from research/analyze_data.py without clashing with this module's name.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT
RESEARCH_DIR = PROJECT_ROOT / "research"
PARENT_ANALYZE = RESEARCH_DIR / "analyze_data.py"
spec = importlib.util.spec_from_file_location("research_analyze_data", PARENT_ANALYZE)
parent_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_mod)  # type: ignore
load_all_sessions = parent_mod.load_all_sessions
remove_spikes = getattr(parent_mod, "remove_spikes", lambda df, col="walking_bpm", window=5, threshold=40: df)

# Output directories for results
RESULTS_DIR = Path(__file__).parent / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
MODELS_DIR = RESULTS_DIR / "models"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# Hyperparameters suited for small datasets
WINDOW_SIZE = 4
TEST_SIZE = 0.2
RANDOM_SEED = 42
N_ESTIMATORS = 300  # 200–400 recommended
LEARNING_RATE = 0.07  # 0.05–0.1 recommended
MAX_DEPTH = 6  # shallow trees
NUM_LEAVES = 31
SUBSAMPLE = 0.8
COLSAMPLE = 0.8
MIN_CHILD_SAMPLES = 10
def filter_true_steps(df):
    """
    Keep only rows marked as true steps if the 'step_event' column exists.
    Accepts boolean or string 'True'/'False'. If column missing, returns df unchanged.
    """
    if "step_event" not in df.columns:
        return df
    mask = df["step_event"]
    if mask.dtype == object:
        mask = mask.astype(str).str.lower() == "true"
    return df[mask].copy()


def filter_bpm_range(df):
    """No-op placeholder (kept for compatibility)."""
    return df


def build_lag_features(df, window_size: int):
    """
    Create sliding window lag features for one-step-ahead prediction.
    """
    sequences, targets = [], []
    for _, group in df.groupby("session_id"):
        values = group["walking_bpm"].values
        for idx in range(window_size, len(values)):
            sequences.append(values[idx - window_size : idx])
            targets.append(values[idx])
    if not sequences:
        return np.array([]), np.array([])
    return np.array(sequences, dtype=np.float32), np.array(targets, dtype=np.float32)


def train_lgbm_model():
    # 1) Load data
    logs_dir = BASE_DIR / "server" / "logs"
    print(f"Loading data from '{logs_dir}'...")
    df = load_all_sessions(str(logs_dir))
    if df.empty:
        print("No data found. Run some sessions first.")
        return

    df = df[df["walking_bpm"] > 0].copy()
    df = filter_true_steps(df)
    df = filter_bpm_range(df)
    df = remove_spikes(df, col="walking_bpm", window=5, threshold=200)
    df = df[df["walking_bpm"] <= 400]
    if df.empty:
        print("No valid walking_bpm values after filtering.")
        return

    # 2) Build features/targets
    X, y = build_lag_features(df, window_size=WINDOW_SIZE)
    if len(X) < 20:
        print(f"Not enough sequences to train (found {len(X)}).")
        return

    # 3) Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED
    )

    # 4) Optional scaling (trees do not need it, but it stabilizes small-data variance)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # 5) Train model
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=N_ESTIMATORS,
        learning_rate=LEARNING_RATE,
        max_depth=MAX_DEPTH,
        num_leaves=NUM_LEAVES,
        subsample=SUBSAMPLE,
        colsample_bytree=COLSAMPLE,
        min_child_samples=MIN_CHILD_SAMPLES,
        random_state=RANDOM_SEED,
    )
    model.fit(X_train, y_train)

    # 6) Evaluate
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print("\nTest Performance")
    print("-" * 40)
    print(f"MAE: {mae:.2f} BPM")
    print(f"R2 : {r2:.3f}")

    # 7) Visualization
    plt.figure(figsize=(12, 5))
    limit = min(200, len(y_test))
    plt.plot(y_test[:limit], label="Actual Next Step", marker="o", markersize=3)
    plt.plot(preds[:limit], label="LGBM Prediction", linestyle="--", linewidth=2)
    r2_pct = r2 * 100
    plt.title(f"LGBM Prediction vs Actual - MAE: {mae:.2f} BPM, R2: {r2:.3f} ({r2_pct:.1f}%)")
    plt.xlabel("Step Index")
    plt.ylabel("BPM")
    plt.legend()
    plt.grid(True, alpha=0.3)
    output_path = PLOTS_DIR / "lgbm_performance.png"
    plt.savefig(output_path)
    print(f"Saved '{output_path}'")

    # 8) Export model + scaler
    artifact = {
        "model": model,
        "scaler": scaler,
        "window_size": WINDOW_SIZE,
        "params": {
            "n_estimators": N_ESTIMATORS,
            "learning_rate": LEARNING_RATE,
            "max_depth": MAX_DEPTH,
            "num_leaves": NUM_LEAVES,
            "subsample": SUBSAMPLE,
            "colsample_bytree": COLSAMPLE,
            "min_child_samples": MIN_CHILD_SAMPLES,
        },
    }
    model_path = MODELS_DIR / "lgbm_model.joblib"
    joblib.dump(artifact, model_path)
    print(f"Model exported to '{model_path}'")
    if len(X_test) > 0:
        example_input = X_test[0].tolist()
        example_prediction = preds[0]
        print(f"Example: input {example_input} -> predicted {example_prediction:.1f} BPM")

    return model, model_path


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
    user_df = filter_bpm_range(user_df)
    user_df = filter_true_steps(user_df)
    user_df = user_df[user_df["walking_bpm"] > 0].copy()
    if user_df.empty:
        raise ValueError("No valid user data after filtering.")

    # Build lag features
    X, y = build_lag_features(user_df, window_size=window_size)
    if len(X) < 10:
        raise ValueError(f"Not enough user sequences to fit calibration head (found {len(X)}).")

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


if __name__ == "__main__":
    train_lgbm_model()

