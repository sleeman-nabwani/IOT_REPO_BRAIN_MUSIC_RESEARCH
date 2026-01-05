"""
Data Analysis Module

Loads session logs and generates visualizations to understand walking patterns.
This is Phase 1 of the KNN research pipeline.

Output:
    - bpm_distribution.png: Histogram + correlation scatter plot
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import glob
import os
import json

# Output directory for results
RESULTS_DIR = Path(__file__).parent / "results"
PLOTS_DIR = RESULTS_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

def _read_session(csv_path: str):
    """
    Read a single session CSV, parse optional # meta line for params,
    attach session_id, smoothing_window, stride, run_type.
    """
    session_id = Path(csv_path).parent.name
    meta = {"smoothing_window": 3, "stride": 1, "run_type": "dynamic"}
    # Read first line for meta
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            first = f.readline()
            if first.startswith("#"):
                tag, _, rest = first.partition(":")
                if tag.strip() == "# meta":
                    meta.update(json.loads(rest.strip()))
    except Exception:
        pass
    try:
        df = pd.read_csv(csv_path, comment="#")
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
        return None
    if df.empty:
        return None
    df["session_id"] = session_id
    df["smoothing_window"] = meta.get("smoothing_window", 3)
    df["stride"] = meta.get("stride", 1)
    df["run_type"] = str(meta.get("run_type", "dynamic"))
    return df


def load_all_sessions(base_dir):
    """
    Scans the directory for all session_data.csv files.
    Returns a combined DataFrame.
    """
    path_pattern = os.path.join(base_dir, "**", "session_data.csv")
    csv_files = glob.glob(path_pattern, recursive=True)
    
    print(f"Found {len(csv_files)} session files.")
    
    dfs = []
    for f in csv_files:
        df = _read_session(f)
        if df is not None:
            dfs.append(df)
            
    if not dfs:
        return pd.DataFrame()
        
    return pd.concat(dfs, ignore_index=True)


def remove_spikes(df, col="walking_bpm", window=5, threshold=40):
    """
    Drop points that deviate from the rolling median by more than `threshold`.
    Keeps edges via min_periods=1. If column missing, returns df unchanged.
    """
    if col not in df.columns:
        return df
    med = df[col].rolling(window=window, center=True, min_periods=1).median()
    mask = (df[col] - med).abs() <= threshold
    return df[mask].copy()

def analyze_intervals():
    # ADJUST THIS PATH to match your actual server/logs/Default location
    logs_dir = r"../server/logs/Default"
    
    print("Loading data...")
    df = load_all_sessions(logs_dir)
    
    if df.empty:
        print("No data found!")
        return

    print(f"Total data points: {len(df)}")
    
    # Clean Data
    # 1. Convert timestamp (HH:MM:SS.mmm) to seconds? 
    # Actually, for KNN, we care about the INTERVAL between steps (BPM).
    # The 'walking_bpm' column is our raw sensor input (or estimated).
    # Let's clean out zeros.
    df = df[df['walking_bpm'] > 0]
    # Remove spikes that are far from local median (stronger threshold for obvious outliers)
    df = remove_spikes(df, col="walking_bpm", window=5, threshold=200)
    # Drop extreme values (hard cutoff) to catch 1000+ BPM misreads
    df = df[df["walking_bpm"] <= 400]
    
    print(f"Valid walking points: {len(df)}")
    
    # VISUALIZATION
    plt.figure(figsize=(10, 6))
    
    # Histogram of BPMs
    plt.subplot(2, 1, 1)
    plt.hist(df['walking_bpm'], bins=50, color='skyblue', edgecolor='black')
    plt.title('Distribution of Walking BPM')
    plt.xlabel('BPM')
    plt.ylabel('Count')
    plt.xlim(0, 1000)
    
    # Scatter: BPM vs Music BPM (How well did we track?)
    plt.subplot(2, 1, 2)
    # Sample a subset so plot isn't too heavy
    sample = df.sample(min(len(df), 2000))
    plt.scatter(sample['walking_bpm'], sample['song_bpm'], alpha=0.3, s=10, label="Samples")
    plt.title('Walking BPM vs Music Response (Correlation)')
    plt.xlabel('User Walking BPM')
    plt.ylabel('Music BPM')
    plt.plot([min(sample['walking_bpm']), max(sample['walking_bpm'])], 
             [min(sample['walking_bpm']), max(sample['walking_bpm'])], 'r--', label="Ideal Identity Line")
    plt.legend()

    plt.tight_layout()
    output_path = PLOTS_DIR / "bpm_distribution.png"
    plt.savefig(output_path)
    print(f"Saved '{output_path}'")
    # plt.show() # Uncomment if running locally with UI

if __name__ == "__main__":
    analyze_intervals()
