"""
LightGBM Data Analysis Module

Loads session logs and generates visualizations to inspect BPM data
before LightGBM training.
"""
import importlib.util
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Load the shared loader from research/analyze_data.py without clashing with this module's name.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = PROJECT_ROOT
RESEARCH_DIR = PROJECT_ROOT / "research"
PARENT_ANALYZE = RESEARCH_DIR / "analyze_data.py"
spec = importlib.util.spec_from_file_location("research_analyze_data", PARENT_ANALYZE)
parent_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_mod)  # type: ignore
load_all_sessions = parent_mod.load_all_sessions

# Output directories for results
RESULTS_DIR = Path(__file__).parent / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def analyze_bpm_distribution():
    """
    Loads all session data and creates basic BPM visualizations.
    """
    logs_dir = BASE_DIR / "server" / "logs"
    print(f"Loading data from '{logs_dir}'...")
    df = load_all_sessions(str(logs_dir))

    if df.empty:
        print("No data found.")
        return

    df = df[df["walking_bpm"] > 0]
    if df.empty:
        print("No valid walking_bpm values after filtering.")
        return

    print(f"Valid walking points: {len(df)}")

    plt.figure(figsize=(10, 6))

    # Histogram of BPMs
    plt.subplot(2, 1, 1)
    plt.hist(df["walking_bpm"], bins=range(0, 651, 5), color="seagreen", edgecolor="black")
    plt.title("Distribution of Walking BPM")
    plt.xlabel("BPM")
    plt.ylabel("Count")
    plt.xlim(0, 650)

    # Scatter: BPM vs Music BPM (sampled)
    plt.subplot(2, 1, 2)
    sample = df.sample(min(len(df), 2000))
    plt.scatter(sample["walking_bpm"], sample["song_bpm"], alpha=0.3, s=10, label="Samples")
    plt.title("Walking BPM vs Music BPM")
    plt.xlabel("User Walking BPM")
    plt.ylabel("Music BPM")
    plt.plot(
        [sample["walking_bpm"].min(), sample["walking_bpm"].max()],
        [sample["walking_bpm"].min(), sample["walking_bpm"].max()],
        "r--",
        label="Ideal Identity Line",
    )
    plt.legend()

    plt.tight_layout()
    output_path = PLOTS_DIR / "lgbm_bpm_distribution.png"
    plt.savefig(output_path)
    print(f"Saved '{output_path}'")


if __name__ == "__main__":
    analyze_bpm_distribution()

