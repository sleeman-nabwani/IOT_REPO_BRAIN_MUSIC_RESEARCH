# Model Options for Next-Step BPM Prediction

## Goal
Predict **only the next walking BPM (one-step-ahead forecast)** from recent steps (and optionally song BPM) with fast real-time inference, easy per-session updates, and a base model that can be specialized per user. This is a time-series, single-horizon prediction task rather than multi-step rollouts.

## Models

### LightGBM Regressor (lag features)
- Pros: Strong accuracy on tabular lag features; millisecond inference; small model; fast retrain per session; minimal code.
- Cons: No true incremental `partial_fit`—retrain on (old + new) data each update.

### XGBoost / CatBoost Regressor (lag features)
- Pros: Competitive accuracy; fast inference; good defaults (CatBoost).
- Cons: No incremental updates; slightly heavier than LightGBM.

### ExtraTrees Regressor (sklearn)
- Pros: Captures nonlinearity; very fast inference; simple.
- Cons: No incremental updates; retrain per session.

### Linear Autoregression with SGDRegressor
- Pros: True `partial_fit` online updates; ultra-lightweight; millisecond inference.
- Cons: Linear capacity—can underfit nonlinear dynamics.

### Small TCN / 1D-CNN (PyTorch/TF)
- Pros: Captures temporal patterns; fast inference when kept small; can fine-tune from a base model.
- Cons: Requires DL dependency and a bit more implementation.

### Compact GRU / LSTM
- Pros: Handles temporal dependencies; can train a base model and fine-tune per user; real-time if small.
- Cons: Heavier than boosting; training time higher; risk of overfitting if too large.

### KNN Regressor (current)
- Pros: Simple; no training time.
- Cons: Inference scales with dataset size; not ideal for low-latency as data grows; no model compression.

## Recommendation
- Primary: LightGBM on lag features (optionally include song BPM). Use shallow trees (max_depth 4–8), 200–500 trees, learning_rate 0.05–0.1. Retrain quickly after each session; save a base model and overwrite a user-specific one if desired.
- If you need true incremental updates without full retrain: add a linear SGDRegressor path.
- If you need more nonlinear capacity and are willing to add DL: use a small TCN/1D-CNN (or compact GRU/LSTM) with a base model + per-user fine-tuning. Compare MAE/R² and latency to LightGBM and adopt the best trade-off.


