from csv import writer
from pathlib import Path
import datetime

class Logger:
    def __init__(self):
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        #setting the path to the logs directory
        self.path = Path(__file__).resolve().parent / "logs" / f"session_{self.timestamp}"
        self.path.mkdir(parents=True, exist_ok=True)
        

        self.file_path = self.path / "session_log.txt"
        self.csv_path = self.path / "session_data.csv"
        #creating the log file
        with self.file_path.open("w", encoding="utf-8") as handle:
            handle.write(f"Session log started at {self.timestamp}\n")
        #creating the csv file
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            csv_writer = writer(handle)
            csv_writer.writerow(["time", "song_bpm", "walking_bpm"])

    def log(self, message: str):
        with self.file_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
        print(message)
            
    def log_csv(self, time: float, song_bpm: float, walking_bpm: float):
        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            csv_writer = writer(handle)
            csv_writer.writerow([time, song_bpm, walking_bpm])