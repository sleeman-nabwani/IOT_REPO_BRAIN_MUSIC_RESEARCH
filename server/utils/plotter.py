import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
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
    
    # get all subfolders recursively that start with "session_"
    sessions = [p for p in logs_dir.rglob("session_*") if p.is_dir()]
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
    try:
        df["seconds"] = df["time"].apply(_elapsed_to_seconds)
        df["seconds"] = pd.to_numeric(df["seconds"], errors='coerce')
    except Exception:
        df["seconds"] = float("nan")
    if "step_event" in df.columns:
        df["step_event"] = (
            df["step_event"].astype(str).str.lower().isin(["true", "1", "yes"])
        )
    else:
        df["step_event"] = True

        df["step_event"] = True

    # Drop invalid rows to prevent plotting errors
    df.dropna(subset=["seconds", "walking_bpm", "song_bpm"], inplace=True)
    # Ensure chronological order (engine may emit out-of-order timestamps)
    try:
        df.sort_values("seconds", inplace=True, kind="mergesort")
        df.reset_index(drop=True, inplace=True)
    except Exception:
        pass

    nan_value = float("nan")
    df["walking_plot"] = pd.to_numeric(df["walking_bpm"], errors='coerce')
    df["song_bpm"] = pd.to_numeric(df["song_bpm"], errors='coerce')
    
    if df.empty:
        print("No valid data to plot.")
        return
    
    # Dynamic styling based on point count to keep lines/points readable
    n_points = len(df)
    lw_main = max(0.6, min(1.4, 500 / max(n_points, 1)))
    marker_size_top = max(3, min(9, 4500 / max(n_points, 1)))
    marker_size_bottom = max(3, min(9, 3500 / max(n_points, 1)))

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
        f"mean |Delta| = {mean_abs_delta:.2f} BPM\n"
        f"max |Delta| = {max_abs_delta:.2f} BPM"
    )
    # print(stats_msg.replace("\n", " | ")) # Optional debug print

    # Process Walking BPM for the line (Smooth, Connect dots)
    # 1. Mask non-steps (ignore decay)
    w_smooth = df["walking_bpm"].where(df["step_event"], float("nan"))
    # 2. Linear Interpolate to connect dots (limit_area='inside' prevents trailing line)
    df["walking_plot"] = w_smooth.interpolate(method='linear', limit_area='inside')

    # Larger figure size for better visibility (Mimic PDF full screen)
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)

    # Walker line restored for static plot (Connected Dots)
    axes[0].plot(
        df["seconds"], df["walking_plot"], label="Walking BPM (sensor)", color="#1f77b4", lw=lw_main
    )
    axes[0].plot(
        df["seconds"], df["song_bpm"], label="Song BPM (player)", color="#ff7f0e", lw=lw_main
    )
    if df["step_event"].any():
        axes[0].scatter(
            df.loc[df["step_event"], "seconds"],
            df.loc[df["step_event"], "walking_bpm"],
            label="Step events",
            color="#22c55e",
            s=marker_size_top,
            alpha=0.85,
            zorder=3,
            marker="o",
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
            s=marker_size_bottom,
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
            s=marker_size_bottom,
            alpha=0.75,
            edgecolors="white",
            linewidths=0.35,
            marker="o",
        )

    axes[1].axhline(0, color="black", linewidth=0.8, linestyle="--")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Delta BPM (song - walking)")
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
    # Save high-definition PDF (preferred for print)
    fig_path_pdf = folder / "BPM_plot.pdf"
    fig.savefig(fig_path_pdf, bbox_inches="tight")
    
    # Save PNG for GUI Viewer (High Res)
    fig_path_png = folder / "BPM_plot.png"
    fig.savefig(fig_path_png, bbox_inches="tight", dpi=120)
    
    print(f"Plot saved to {fig_path_png}")
    
    # Clean up memory
    plt.close(fig)


# ==================================================================================
# LIVE PLOTTER CLASS
# This class manages the real-time drawing of the graph in the GUI.
# It uses an "Optimized Update" strategy (lines.set_data) to prevent flickering.
# ==================================================================================

class LivePlotter:
    def __init__(self, ax1, theme_colors):
        """
        Initialize the plotter with the main axis and the color theme.
        ax1: Top plot (BPM)
        """
        self.ax1 = ax1
        # self.ax2 removed (Single plot mode)
        self.P = theme_colors
        
        # Persistent Line Objects
        # We store these so we can just update their data later instead of recreating them.
        self.line_walker = None 
        self.line_song = None 
        self.line_double = None
        self.line_half = None
        self.scat_steps = None
        
        self.show_double = False
        self.show_half = False
        self.hold_seconds = 6  # unused now; retained for tuning if needed
        self.max_render_points = 3500  # downsample target to keep UI smooth
        self.max_scatter_points = 1800
        self.view_window_sec = 240  # sliding window span for live view

        # Track maximum X value seen to prevent graph from shrinking/resetting
        self.max_x_seen = 10  # Start with 10 seconds as minimum view
        
        # Apply the initial grid/labels/colors once at startup
        self._style_axes(self.ax1, "LIVE BPM TRACE", "BPM", show_x=True)
        
        # Set initial X-axis limit (Y will auto-scale)
        self.ax1.set_xlim(0, self.max_x_seen)
        self.ax1.set_ylim(0, 160) # Initial view
        
    def reset(self):
        """Clear all plotted data and reset axes limits."""
        self.max_x_seen = 10
        lw = getattr(self, "line_walker", None)
        ls = getattr(self, "line_song", None)
        ld = getattr(self, "line_double", None)
        lh = getattr(self, "line_half", None)
        sc = getattr(self, "scat_steps", None)

        if lw is not None:
            lw.set_data([], [])
        if ls is not None:
            ls.set_data([], [])
        if ld is not None:
            ld.set_data([], [])
        if lh is not None:
            lh.set_data([], [])
        if sc is not None:
            try:
                sc.remove()
            except Exception:
                pass
            self.scat_steps = None
        self.ax1.set_xlim(0, self.max_x_seen)
        self.ax1.set_ylim(0, 160)
        self.ax1.figure.canvas.draw_idle()

    def set_show_multipliers(self, double, half):
        self.show_double = double
        self.show_half = half

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
        if df.empty:
            return
            
        # Ensure numeric types (handle "2400.00" strings or NaNs)
        t = pd.to_numeric(df["seconds"], errors='coerce')
        w = pd.to_numeric(df["walking_bpm"], errors='coerce')
        s = pd.to_numeric(df["song_bpm"], errors='coerce')
        step_events = df["step_event"].copy() if "step_event" in df.columns else pd.Series([False] * len(df))
        
        # Drop rows where time or song_bpm is NaN
        valid_mask = t.notna() & s.notna()
        t = t[valid_mask].reset_index(drop=True)
        w = w[valid_mask].reset_index(drop=True)
        s = s[valid_mask].reset_index(drop=True)
        step_events = step_events[valid_mask].reset_index(drop=True)

        # Ensure monotonic time for plotting (handles out-of-order packets)
        try:
            order = t.argsort(kind="mergesort")
            t = t.iloc[order].reset_index(drop=True)
            w = w.iloc[order].reset_index(drop=True)
            s = s.iloc[order].reset_index(drop=True)
            step_events = step_events.iloc[order].reset_index(drop=True)
        except Exception:
            pass
        
        if len(t) == 0:
            return
        
        # Downsample to keep draw calls light while keeping the full session span
        if len(t) > self.max_render_points:
            idx = pd.Index(np.linspace(0, len(t) - 1, self.max_render_points, dtype=int))
            t = t.iloc[idx].reset_index(drop=True)
            w = w.iloc[idx].reset_index(drop=True)
            s = s.iloc[idx].reset_index(drop=True)
            step_events = step_events.iloc[idx].reset_index(drop=True)
        
        # Song BPM: allow it to show even before steps, fill gaps
        s = s.ffill().bfill()

        # Force a starting point at t=0 for song BPM
        if len(t) == 0:
            return
        if t.iloc[0] > 0 or pd.isna(t.iloc[0]):
            t = pd.concat([pd.Series([0.0]), t], ignore_index=True)
            s = pd.concat([pd.Series([s.iloc[0]]), s], ignore_index=True)
            w = pd.concat([pd.Series([float("nan")]), w], ignore_index=True)
            step_events = pd.concat([pd.Series([False]), step_events], ignore_index=True)

        # Walking BPM: show only where steps occurred, connect gaps only between steps
        w = w.where(step_events, float("nan"))
        w = w.interpolate(method='linear', limit_area='inside')  # connect between step events only
        
        # --- PLOT 1: BPM (Top) ---
        if self.line_song is None:
            # First run: Initialize the Line2D objects
            self.line_walker, = self.ax1.plot(t, w, color="#1f77b4", lw=2, label="Walker")
            self.line_song, = self.ax1.plot(t, s, color="#10b981", lw=2, ls="--", label="Music")
            
            # Additional optional reference lines
            self.line_double, = self.ax1.plot([], [], color="#8b5cf6", lw=1.5, ls=":", label="2x Song", alpha=0.7)
            self.line_half, = self.ax1.plot([], [], color="#ec4899", lw=1.5, ls=":", label="0.5x Song", alpha=0.7)
            
            self.ax1.legend(facecolor=self.P["card_bg"], labelcolor="white", frameon=False, fontsize=8, loc="upper left")
            
            # Initialize scatter once; we will update offsets for performance
            self.scat_steps = self.ax1.scatter([], [], color="#f59e0b", s=12, zorder=5)
        else:
            # Lines will be updated after scatter so points appear first
            pass
            
        # X-axis: sliding window based on view_window_sec
        current_max = t.max() if len(t) > 0 else 0
        self.max_x_seen = current_max
        x_min = max(0, current_max - getattr(self, "view_window_sec", 240))
        self.ax1.set_xlim(x_min, current_max + 5)
        
        # Calculate multiples
        s_double = s * 2
        s_half = s * 0.5
        
        # Y-axis Auto-Scaling
        # We need to account for the new lines if they are visible
        max_s = s.max() if len(s) > 0 and not pd.isna(s.max()) else 0
        max_w = w.max() if len(w) > 0 and not pd.isna(w.max()) else 0
        
        current_max = max(max_s, max_w)
        if self.show_double: 
            max_d = s_double.max() if len(s_double)>0 else 0
            current_max = max(current_max, max_d)
        
        # Determine new upper limit (at least 160)
        new_ymax = max(160, current_max + 10)
        self.ax1.set_ylim(0, new_ymax)

        # Scatter points (Footsteps) - with safety guards and recent-window limit
        try:
            if step_events.any():
                step_mask = step_events.fillna(False)
                step_t = t[step_mask]
                step_w = w[step_mask]
                
                # Downsample footsteps to keep draw time predictable
                if len(step_t) > self.max_scatter_points:
                    idx = pd.Index(np.linspace(0, len(step_t) - 1, self.max_scatter_points, dtype=int))
                    step_t = step_t.iloc[idx].reset_index(drop=True)
                    step_w = step_w.iloc[idx].reset_index(drop=True)
                
                offsets = np.column_stack((step_t.to_numpy(), step_w.to_numpy()))
            else:
                offsets = np.empty((0, 2))

            if self.scat_steps is not None:
                self.scat_steps.set_offsets(offsets)
            else:
                self.scat_steps = self.ax1.scatter([], [], color="#f59e0b", s=12, zorder=5)
                self.scat_steps.set_offsets(offsets)
        except Exception:
            pass  # Silently ignore scatter errors to prevent crashes

        # Update lines
        if self.line_song is not None:
            self.line_walker.set_data(t, w)
            self.line_song.set_data(t, s)
            
            if self.show_double:
                self.line_double.set_data(t, s_double)
            else:
                self.line_double.set_data([], [])
                
            if self.show_half:
                self.line_half.set_data(t, s_half)
            else:
                self.line_half.set_data([], [])

    def finalize_plot(self, df):
        """
        Called when session stops to draw the final connected line.
        """
        if df.empty or self.line_walker is None: return
        
        # Ensure numeric
        t = pd.to_numeric(df["seconds"], errors='coerce')
        w = pd.to_numeric(df["walking_bpm"], errors='coerce')
        step_events = df["step_event"].copy() if "step_event" in df.columns else pd.Series([False]*len(df))

        # Ensure monotonic time for final connected line
        try:
            valid_mask = t.notna()
            t = t[valid_mask].reset_index(drop=True)
            w = w[valid_mask].reset_index(drop=True)
            step_events = step_events[valid_mask].reset_index(drop=True)
            order = t.argsort(kind="mergesort")
            t = t.iloc[order].reset_index(drop=True)
            w = w.iloc[order].reset_index(drop=True)
            step_events = step_events.iloc[order].reset_index(drop=True)
        except Exception:
            pass
        
        # Mask & Interpolate (Connect dots, NO trailing line)
        w_smooth = w.where(step_events, float("nan"))
        w_final = w_smooth.interpolate(method='linear', limit_area='inside')
        
        # Update line with full connected path
        self.line_walker.set_data(t, w_final)


if __name__ == "__main__":
    try:
        df, folder = load_latest_csv()
        save_static_plot(df, folder)
    except Exception as e:
        print(f"Error: {e}")
        plt.close()
        exit(1)