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
        self.buffer = None
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
        else:
            raise ValueError("Invalid LightGBM model file")
        self.buffer = deque(maxlen=self.window)

    def add_step(self, bpm):
        if self.buffer is None:
            return
        with self._lock:
            self.buffer.append(float(bpm))

    def predict_next(self):
        if not self.model or self.buffer is None:
            return None
        with self._lock:
            if len(self.buffer) < self.window:
                return None
            buf = list(self.buffer)
        X = np.array([buf], dtype=float)
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
        window_vals = np.full((1, self.window), bpm, dtype=float)
        X_scaled = self.scaler.transform(window_vals)
        # Ignore the output; the call warms up internal caches/threads.
        _ = self.model.predict(X_scaled)

