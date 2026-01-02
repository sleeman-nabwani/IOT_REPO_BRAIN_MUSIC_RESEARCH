# LightGBM Per-User Calibration Head

This describes how to train and use the lightweight linear head on top of the base LightGBM model for user personalization.

## Prerequisites
- Base LightGBM model artifact produced by `research\LightGBM\run_lgbm.bat` (saves `results\models\lgbm_model.joblib`).
- Virtual environment `.venv` present in project root.

## Train a user head
From the repo root:
```
research\LightGBM\run_lgbm_user_head.bat "User Name" [suffix]
```
- If you omit `suffix`, it defaults to the user name with spaces replaced by underscores.
- The first argument can be:
  - A user name (looks under `server\logs\<user>\**\session_data.csv`)
  - A directory containing session_data.csv files
  - A single CSV file with at least `walking_bpm` (if `session_id` missing, a dummy one is added)

The head artifact is saved to:
```
research\LightGBM\results\models\lgbm_user_head_<suffix>.joblib
```

## What happens during training
1) Loads the base LightGBM artifact (model, scaler, window size).
2) Loads all session_data.csv for the user (or the provided CSV), filters BPM to a sane range, and builds lag features.
3) Gets base LightGBM predictions on scaled lags.
4) Trains a Ridge head on `[base_pred, scaled lags]`.
5) Reports validation MAE/R² and saves the head artifact.

## Using the head for inference (Python sketch)
```python
import joblib, numpy as np
from research.LightGBM.train_lgbm import build_lag_features

base = joblib.load("research/LightGBM/results/models/lgbm_model.joblib")
head = joblib.load("research/LightGBM/results/models/lgbm_user_head_SonicWesh.joblib")

base_model = base["model"]
scaler = base["scaler"]
window = base["window_size"]
calibrator = head["calibrator"]

# df_user_new must contain walking_bpm and session_id
X, _ = build_lag_features(df_user_new, window)
X_scaled = scaler.transform(X)
base_preds = base_model.predict(X_scaled)
features = np.column_stack([base_preds, X_scaled])
user_preds = calibrator.predict(features)
```

## Notes
- Always quote names with spaces.
- Keep BPM filtering to reduce outlier impact (defaults 30–250 in the code).
- For best results, ensure user data has enough sequences (the code requires at least 10).  

