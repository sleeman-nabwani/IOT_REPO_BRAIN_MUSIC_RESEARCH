from pathlib import Path
from collections import deque
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
        if self.buffer is not None:
            self.buffer.append(float(bpm))

    def predict_next(self):
        if not self.model or len(self.buffer) < self.window:
            return None
        X = np.array([list(self.buffer)], dtype=float)
        X_scaled = self.scaler.transform(X)
        return float(self.model.predict(X_scaled)[0])


