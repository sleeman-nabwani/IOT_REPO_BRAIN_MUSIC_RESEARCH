from csv import writer
from pathlib import Path
import datetime
import time


def _format_elapsed(seconds: float) -> str:
    #formats the time to look like stopper-style HH:MM:SS.mmm
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

class Logger:
    # NOTE: This logger is used both for the console and for the GUI.
    #       It is initialized with a GUI callback if available.
    def __init__(self, gui_callback=None, session_name=None):
        self.start_time = time.time()
        if session_name and session_name.strip():
            # Sanitize name
            safe_name = "".join([c for c in session_name if c.isalnum() or c in (' ', '_', '-')]).strip()
            # New Structure: logs/NAME (Flattened - Overwrites/Updates existing folder)
            self.path = Path(__file__).resolve().parent / "logs" / safe_name
        else:
            # Default Structure: logs/session_TIMESTAMP
            self.path = Path(__file__).resolve().parent / "logs" / f"session_{self.timestamp}"

        #setting the path to the logs directory
        self.path.mkdir(parents=True, exist_ok=True)
        
        self.file_path = self.path / "session_log.txt"
        self.csv_path = self.path / "session_data.csv"
        #creating the log file
        with self.file_path.open("w", encoding="utf-8") as handle:
            handle.write(f"Session log started at {self.timestamp} (t=0.000)\n")
        #creating the csv file
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            csv_writer = writer(handle)
            csv_writer.writerow(["time", "song_bpm", "walking_bpm", "step_event"])

    def _elapsed_str(self, timestamp: float | None = None) -> str:
        if timestamp is None:
            timestamp = time.time()
        elapsed = max(0.0, timestamp - self.start_time)
        return _format_elapsed(elapsed)

    def log(self, message: str):
        stamped = f"[{self._elapsed_str()}] {message}"
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(stamped + "\n")
        print(stamped)
        
        # Update GUI if callback is provided
        if self.gui_callback:
            self.gui_callback(message)
            
    def log_csv(
        self, timestamp: float, song_bpm: float, walking_bpm: float, step_event: bool = False):
        elapsed = self._elapsed_str(timestamp)
        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            csv_writer = writer(handle)
            csv_writer.writerow([elapsed, song_bpm, walking_bpm, step_event])