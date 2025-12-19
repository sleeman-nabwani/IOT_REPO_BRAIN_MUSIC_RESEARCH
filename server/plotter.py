import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sys import exit

# ==================================================================================
# STATIC UTILITY FUNCTIONS
# These handle finding the log files on disk and converting timestamps.
# ==================================================================================

def find_latest_session_folder():
    """Locates the most recently created session folder in the /logs directory."""
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


def generate_post_session_plot(folder_path):
    """
    Reads the CSV from the given session folder and saves a static PNG plot.
    This is called by the GUI when the session stops.
    """
    folder = Path(folder_path)
    csv_path = folder / "session_data.csv"
    if not csv_path.exists():
        print(f"No CSV found in {folder}, skipping plot.")
        return

    try:
        df = pd.read_csv(csv_path)
        save_static_plot(df, folder)
    except Exception as e:
        print(f"Failed to generate plot: {e}")


def save_static_plot(df, folder):
    """
    Generates a Matplotlib figure from the data and saves it as a PNG file.
    Does NOT show the window (non-blocking).
    """
    df = df.copy()
    df["seconds"] = df["time"].apply(_elapsed_to_seconds)
    if "step_event" in df.columns:
        df["step_event"] = (
            df["step_event"].astype(str).str.lower().isin(["true", "1", "yes"])
        )
    else:
        df["step_event"] = True

    nan_value = float("nan")
    df["walking_plot"] = pd.to_numeric(df["walking_bpm"], errors='coerce')
    df["song_bpm"] = pd.to_numeric(df["song_bpm"], errors='coerce')
    
    # Calculate delta
    df["delta_step_only"] = (df["song_bpm"] - df["walking_plot"]).where(df["step_event"], nan_value)
    df["abs_delta"] = df["delta_step_only"].abs()

    # Safe stats calculation
    try:
        mean_abs_delta = df["abs_delta"].mean(skipna=True)
        max_abs_delta = df["abs_delta"].max(skipna=True)
        if pd.isna(mean_abs_delta): mean_abs_delta = 0.0
        if pd.isna(max_abs_delta): max_abs_delta = 0.0
    except:
        mean_abs_delta = 0.0
        max_abs_delta = 0.0

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

    fig_path = folder / "BPM_plot.png"
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"Plot saved to {fig_path}")
    
    # Clean up memory
    plt.close(fig)


# ==================================================================================
# LIVE PLOTTER CLASS
# This class manages the real-time drawing of the graph in the GUI.
# It uses an "Optimized Update" strategy (lines.set_data) to prevent flickering.
# ==================================================================================

class LivePlotter:
    def __init__(self, ax1, ax2, theme_colors):
        """
        Initialize the plotter with the two axes (plots) and the color theme.
        ax1: Top plot (BPM)
        ax2: Bottom plot (Delta/Sync)
        """
        self.ax1 = ax1
        self.ax2 = ax2
        self.P = theme_colors
        
        # Persistent Line Objects
        # We store these so we can just update their data later instead of recreating them.
        self.line_walker = None
        self.line_song = None
        
        # Delta Plot Objects (Line)
        self.line_delta = None
        self.fill_tolerance = None
        self.scat_steps = None
        
        # Apply the initial grid/labels/colors once at startup
        self._style_axes(self.ax1, "LIVE BPM TRACE", "BPM", show_x=False)
        self._style_axes(self.ax2, "SYNC DELTA (Dots = Steps)", "Delta (Song - Walking)", show_x=True)

    def _style_axes(self, ax, title, ylabel, show_x=False):
        """Applies the dark theme, grid lines, and removes borders for a clean look."""
        P = self.P
        ax.set_facecolor(P["card_bg"])
        ax.set_title(title, color=P["text_sub"], fontsize=9, fontweight="bold", loc="left", pad=10)
        ax.set_ylabel(ylabel, color=P["text_sub"], fontsize=8)
        
        for s in ["top", "right", "left"]: 
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(P["border"])
        
        ax.tick_params(axis='x', colors=P["text_sub"], labelsize=8)
        ax.tick_params(axis='y', colors=P["text_sub"], labelsize=8)
        ax.yaxis.grid(True, color=P["border"], ls='--', alpha=0.5)
        ax.xaxis.grid(False)
        
        if show_x:
            ax.set_xlabel("Time (s)", color=P["text_sub"], fontsize=8)
        else:
            ax.tick_params(axis='x', labelbottom=False, bottom=False)

    def update(self, df):
        """
        Called every 100ms by the GUI.
        Receives a pandas DataFrame 'df' with the latest session data.
        Updates the graph lines efficiently.
        """
        # Ensure numeric types (handle "2400.00" strings or NaNs)
        t = pd.to_numeric(df["seconds"], errors='coerce')
        w = pd.to_numeric(df["walking_bpm"], errors='coerce')
        s = pd.to_numeric(df["song_bpm"], errors='coerce')
        
        # Drop rows where critical data is NaN to prevent plotting errors
        # (Optional: fillna(0) if preferred, but dropping is cleaner for graphs)
        valid_mask = t.notna() & w.notna() & s.notna()
        t = t[valid_mask]
        w = w[valid_mask]
        s = s[valid_mask]
        
        # --- PLOT 1: BPM (Top) ---
        if self.line_walker is None:
            # First run: Initialize the Line2D objects
            self.line_walker, = self.ax1.plot(t, w, color="#3b82f6", lw=2, label="Walker")
            self.line_song, = self.ax1.plot(t, s, color="#10b981", lw=2, ls="--", label="Music")
            self.ax1.legend(facecolor=self.P["card_bg"], labelcolor="white", frameon=False, fontsize=8)
        else:
            # Subsequent runs: Just update x and y data (Fast!)
            self.line_walker.set_data(t, w)
            self.line_song.set_data(t, s)
            
        # Re-calculate limits so the graph zooms out as time passes
        self.ax1.relim()
        self.ax1.autoscale_view()

        # Scatter points (Footsteps)
        # For scatter, it's easier to remove and redraw the collection than update it.
        if self.scat_steps: self.scat_steps.remove()
        if df["step_event"].any(): 
            sub = df[df["step_event"]]
            self.scat_steps = self.ax1.scatter(sub["seconds"], sub["walking_bpm"], color="white", s=15, zorder=5)

        # --- PLOT 2: DELTA (Bottom) ---
        # Calculate Delta ONLY where step_event is True
        # We need the full delta array for indexing, but we only plot points at step events
        
        # 1. Background Tolerance Band (+/- 2 BPM)
        # We redraw this to fit the time axis
        if self.fill_tolerance: self.fill_tolerance.remove()
        self.fill_tolerance = self.ax2.fill_between(t, -2, 2, color="#f2f2f2", alpha=0.1, label="Tolerance (±2)")

        # 2. Continuous Line Plot
        delta = s - w
        if self.line_delta is None:
            self.line_delta, = self.ax2.plot(t, delta, color="#a855f7", lw=1.5, label="Sync Error") # Purple line
        else:
            self.line_delta.set_data(t, delta)

        self.ax2.axhline(0, color=self.P["text_sub"], ls="--", lw=1, alpha=0.3)
        self.ax2.relim()
        self.ax2.autoscale_view()
        
        # Update Legend (Only if handlers exist)
        # We do this every frame to ensure labels are correct if points appear/disappear
        handles, labels = self.ax2.get_legend_handles_labels()
        # Filter duplicates in legend
        by_label = dict(zip(labels, handles))
        self.ax2.legend(by_label.values(), by_label.keys(), facecolor=self.P["card_bg"], labelcolor="white", frameon=False, fontsize=8, loc="upper right")


if __name__ == "__main__":
    try:
        df, folder = load_latest_csv()
        save_static_plot(df, folder)
    except Exception as e:
        print(f"Error: {e}")
        plt.close()
        exit(1)