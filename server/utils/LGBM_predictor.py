from pathlib import Path
from collections import deque
import threading
import joblib
import numpy as np


class LGBMPredictor:
    """
    LightGBM-based next-step predictor using lag features.
    Loads the base model artifact exported by research/LightGBM/train_lgbm.py
    (expects keys: model, scaler, window_size).
    """

    def __init__(self, model_path=None):
        default = (
            Path(__file__).resolve().parent.parent.parent
            / "research"
            / "LightGBM"
            / "results"
            / "models"
            / "lgbm_model.joblib"
        )
        self.model_path = Path(model_path or default)
        self.model = None
        self.scaler = None
        self.window = None
        self.extra_feature_names = ["smoothing_window", "stride"]
        self.buffer = None  # deque of tuples: (walking_bpm, instant_bpm)
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        payload = joblib.load(self.model_path)
        if isinstance(payload, dict) and "model" in payload and "scaler" in payload and "window_size" in payload:
            self.model = payload["model"]
            self.scaler = payload["scaler"]
            self.window = int(payload["window_size"])
            schema = payload.get("feature_schema")
            if schema and "extra" in schema:
                self.extra_feature_names = schema["extra"]
        else:
            raise ValueError("Invalid LightGBM model file")
        self.buffer = deque(maxlen=self.window)

    def add_step(self, walking_bpm, instant_bpm=None):
        if self.buffer is None:
            return
        with self._lock:
            if instant_bpm is None:
                instant_bpm = walking_bpm
            self.buffer.append((float(walking_bpm), float(instant_bpm)))

    def predict_next(self, smoothing_window: float | int = 3, stride: float | int = 1):
        if not self.model or self.buffer is None:
            return None
        with self._lock:
            if len(self.buffer) < self.window:
                return None
            buf = list(self.buffer)
        extras = [float(smoothing_window), float(stride)]
        # Flatten: walk lags then instant lags
        walk_lags = [p[0] for p in buf]
        inst_lags = [p[1] for p in buf]
        X = np.array([walk_lags + inst_lags + extras], dtype=float)
        X_scaled = self.scaler.transform(X)
        return float(self.model.predict(X_scaled)[0])

    def warmup(self, initial_bpm: float | None = None):
        """
        Run a single inference on a synthetic window to pay model/scaler warm-up
        costs upfront. Does not mutate the live buffer.
        """
        if not self.model or self.window is None or self.scaler is None:
            return
        bpm = float(initial_bpm) if initial_bpm is not None else 0.0
        walk = np.full((self.window,), bpm, dtype=float)
        inst = np.full((self.window,), bpm, dtype=float)
        extras = np.array([3.0, 1.0], dtype=float)
        row = np.concatenate([walk, inst, extras])
        X_scaled = self.scaler.transform(row.reshape(1, -1))
        # Ignore the output; the call warms up internal caches/threads.
        _ = self.model.predict(X_scaled)

