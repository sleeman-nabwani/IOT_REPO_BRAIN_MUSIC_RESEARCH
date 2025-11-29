import serial
import time
import csv
import os

# ========= CONFIG ========= #
PORT = "COM5"       
BAUD = 115200
OUT_DIR = "data_logs"
# ========================== #

# Create unique filename per session
timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
fname = f"esp_log_{timestamp}.csv"

os.makedirs(OUT_DIR, exist_ok=True)
fpath = os.path.join(OUT_DIR, fname)

print(f"Logging to -> {fpath}")

# Open serial + csv file
with serial.Serial(PORT, BAUD, timeout=1) as ser, \
     open(fpath, "w", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)
    writer.writerow(["pc_time_sec", "raw_line"])  # Column header

    print("\nListening... Press CTRL+C to stop.\n")

    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            now = time.time()
            writer.writerow([now, line])
            f.flush()

            print(now, "|", line)

    except KeyboardInterrupt:
        print("\nSession ended. File saved.")
