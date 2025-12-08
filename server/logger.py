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
    def __init__(self):
        self.start_time = time.time()
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        #setting the path to the logs directory
        self.path = Path(__file__).resolve().parent / "logs" / f"session_{self.timestamp}"
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
            
    def log_csv(
        self, timestamp: float, song_bpm: float, walking_bpm: float, step_event: bool = False):
        elapsed = self._elapsed_str(timestamp)
        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            csv_writer = writer(handle)
            csv_writer.writerow([elapsed, song_bpm, walking_bpm, step_event])