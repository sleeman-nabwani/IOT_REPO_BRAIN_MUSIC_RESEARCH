from pathlib import Path
from collections import deque
import joblib

class KNNPredictor:
    def __init__(self, model_path=None):
        default = Path(__file__).resolve().parent.parent.parent / "research" / "results" / "models" / "knn_model.joblib"
        self.model_path = Path(model_path or default)
        self.model = None
        self.window = None
        self.buffer = None
        self._load()

    def _load(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        payload = joblib.load(self.model_path)
        if isinstance(payload, dict) and "model" in payload and "window" in payload:
            self.model = payload["model"]
            self.window = int(payload["window"])
        else:
            raise ValueError("Invalid model file")
        self.buffer = deque(maxlen=self.window)

    def add_step(self, bpm):
        if self.buffer is not None:
            self.buffer.append(float(bpm))

    def predict_next(self):
        if not self.model or len(self.buffer) < self.window:
            return None
        return float(self.model.predict([list(self.buffer)])[0])