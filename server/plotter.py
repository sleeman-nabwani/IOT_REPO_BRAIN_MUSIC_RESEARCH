import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sys import exit

def find_latest_session_folder():
    logs_dir = Path(__file__).resolve().parent / "logs"
    if not logs_dir.exists():
        raise FileNotFoundError("No 'logs' folder found.")
    
    # get all subfolders: session_*
    sessions = [p for p in logs_dir.iterdir() if p.is_dir()]
    if not sessions:
        raise FileNotFoundError("No session folders found inside /logs.")
    
    # sort by modification time, newest first
    latest = max(sessions, key=lambda p: p.stat().st_mtime)
    return latest

def load_latest_csv():
    session_folder = find_latest_session_folder()
    csv_path = session_folder / "session_data.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No CSV found in {session_folder}")
    
    print(f"Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    return df, session_folder

def _elapsed_to_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)


def plot_data(df, folder):
    df = df.copy()
    df["seconds"] = df["time"].apply(_elapsed_to_seconds)
    df["delta"] = df["song_bpm"] - df["walking_bpm"]
    df["abs_delta"] = df["delta"].abs()

    mean_abs_delta = df["abs_delta"].mean()
    max_abs_delta = df["abs_delta"].max()
    p95_abs_delta = df["abs_delta"].quantile(0.95)

    stats_msg = (
        "Tracking error stats (song - walking BPM)\n"
        f"mean |Δ| = {mean_abs_delta:.2f} BPM\n"
        f"max  |Δ| = {max_abs_delta:.2f} BPM\n"
        f"p95  |Δ| = {p95_abs_delta:.2f} BPM"
    )
    print(stats_msg.replace("\n", " | "))

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(
        df["seconds"], df["walking_bpm"], label="Walking BPM (sensor)", color="#1f77b4"
    )
    axes[0].plot(
        df["seconds"], df["song_bpm"], label="Song BPM (player)", color="#ff7f0e"
    )
    axes[0].set_ylabel("BPM")
    axes[0].set_title(f"BPM Tracking\n{folder.name}")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(
        df["seconds"], df["delta"], label="Δ = song - walking", color="#d62728"
    )
    axes[1].fill_between(
        df["seconds"],
        df["delta"],
        0,
        where=df["delta"] >= 0,
        color="#ff9896",
        alpha=0.3,
        interpolate=True,
        label="Song faster",
    )
    axes[1].fill_between(
        df["seconds"],
        df["delta"],
        0,
        where=df["delta"] < 0,
        color="#9edae5",
        alpha=0.3,
        interpolate=True,
        label="Song slower",
    )
    axes[1].axhline(0, color="black", linewidth=0.8, linestyle="--")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Δ BPM (song - walking)")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    fig.text(
        0.99,
        0.02,
        stats_msg,
        ha="right",
        va="bottom",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig_path = folder / "BPM_plot.png"
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {fig_path}")

    plt.show()
    plt.close(fig)

if __name__ == "__main__":
    try:
        df, folder = load_latest_csv()
        plot_data(df, folder)
    except Exception as e:
        print(f"Error: {e}")
        plt.close()
        exit(1)