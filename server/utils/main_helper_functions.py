"""
Main Engine Helper Functions

Utility functions used by main.py for session management and post-processing.
"""
import sys
import subprocess
from pathlib import Path
from .safety import safe_execute


@safe_execute
def retrain_prediction_model():
    """
    Auto-retrain prediction model after session ends.
    Primary: LightGBM (research/LightGBM/train_lgbm.py).
    Fallback: KNN (research/train_knn.py) if LightGBM script is missing.
    """
    research_dir = Path(__file__).parent.parent.parent / "research"
    train_lgbm = research_dir / "LightGBM" / "train_lgbm.py"
    train_knn = research_dir / "train_knn.py"

    target_script = None
    if train_lgbm.exists():
        target_script = train_lgbm
    elif train_knn.exists():
        target_script = train_knn

    if target_script:
        print(f"[Prediction] Retraining model with new data using {target_script.name}...")
        result = subprocess.run(
            [sys.executable, str(target_script)],
            cwd=str(research_dir),
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print("[Prediction] Model updated successfully!")
        else:
            print(f"[Prediction] Training failed: {result.stderr[:200]}")
