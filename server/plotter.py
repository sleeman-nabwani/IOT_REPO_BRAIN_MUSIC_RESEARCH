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
    if "step_event" in df.columns:
        df["step_event"] = (
            df["step_event"].astype(str).str.lower().isin(["true", "1", "yes"])
        )
    else:
        df["step_event"] = True

    nan_value = float("nan")
    df["walking_plot"] = df["walking_bpm"]
    df["delta_step_only"] = (df["song_bpm"] - df["walking_bpm"]).where(df["step_event"], nan_value)
    df["abs_delta"] = df["delta_step_only"].abs()

    mean_abs_delta = df["abs_delta"].mean(skipna=True)
    max_abs_delta = df["abs_delta"].max(skipna=True)
    stats_msg = (
        "Tracking error stats (song - walking BPM)\n"
        f"mean |Δ| = {mean_abs_delta:.2f} BPM\n"
        f"max  |Δ| = {max_abs_delta:.2f} BPM"
    )
    print(stats_msg.replace("\n", " | "))

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(
        df["seconds"], df["walking_plot"], label="Walking BPM (sensor)", color="#1f77b4"
    )
    axes[0].plot(
        df["seconds"], df["song_bpm"], label="Song BPM (player)", color="#ff7f0e"
    )
    if df["step_event"].any():
        axes[0].scatter(
            df.loc[df["step_event"], "seconds"],
            df.loc[df["step_event"], "walking_bpm"],
            label="Step events",
            color="#2ca02c",
            s=18,
            alpha=0.6,
            zorder=3,
            marker="o",
            edgecolors="white",
            linewidths=0.3,
        )
    axes[0].set_ylabel("BPM")
    axes[0].set_title(f"BPM Tracking\n{folder.name}")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    step_mask = df["step_event"] & df["delta_step_only"].notna()
    step_times = df.loc[step_mask, "seconds"]
    step_deltas = df.loc[step_mask, "delta_step_only"]
    pos_mask = step_deltas > 0
    neg_mask = step_deltas < 0

    # optional tolerance band for visual guidance (e.g., ±2 BPM)
    tol = 2
    axes[1].fill_between(
        step_times,
        -tol,
        tol,
        color="#f2f2f2",
        alpha=0.6,
        step="mid",
        label="±2 BPM band",
    )

    if pos_mask.any():
        axes[1].scatter(
            step_times[pos_mask],
            step_deltas[pos_mask],
            label="Song faster",
            color="#d62728",
            s=22,
            alpha=0.75,
            edgecolors="white",
            linewidths=0.35,
            marker="o",
        )
    if neg_mask.any():
        axes[1].scatter(
            step_times[neg_mask],
            step_deltas[neg_mask],
            label="Song slower",
            color="#1f77b4",
            s=22,
            alpha=0.75,
            edgecolors="white",
            linewidths=0.35,
            marker="o",
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