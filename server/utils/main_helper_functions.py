"""
Main Engine Helper Functions

Utility functions used by main.py for session management and post-processing.
"""
import sys
import subprocess
from pathlib import Path
from .safety import safe_execute


@safe_execute
def retrain_knn_model():
    """
    Auto-retrain KNN model after session ends.
    Uses the latest session data to improve predictions.
    """
    research_dir = Path(__file__).parent.parent.parent / "research"
    train_script = research_dir / "train_knn.py"
    
    if train_script.exists():
        print("[KNN] Retraining model with new data...")
        result = subprocess.run(
            [sys.executable, str(train_script)],
            cwd=str(research_dir),
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print("[KNN] Model updated successfully!")
        else:
            print(f"[KNN] Training failed: {result.stderr[:200]}")
