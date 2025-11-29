import serial
import time
import os
import matplotlib.pyplot as plt

# ========= USER CONFIG ========= #
PORT = "COM5"              # set your COM port
BAUD = 115200
OUT_DATA_DIR = "data_logging"
OUT_PLOT_DIR = "plots"

MIN_FSR = 0
MAX_FSR = 5000
# =============================== #


def main():
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    log_name = f"esp_steps_{timestamp}.csv"
    plot_name = f"steps_plot_{timestamp}.png"

    os.makedirs(OUT_DATA_DIR, exist_ok=True)
    os.makedirs(OUT_PLOT_DIR, exist_ok=True)

    log_path = os.path.join(OUT_DATA_DIR, log_name)
    plot_path = os.path.join(OUT_PLOT_DIR, plot_name)

    print(f"\nLogging session -> {log_path}")
    print("Press CTRL+C to stop the session.\n")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except Exception as e:
        print(f"Could not open serial port {PORT}: {e}")
        return

    t0 = None
    times = []          # seconds since first step
    feet = []           # 1 or 2
    fsr_values = []     # peak sensor value
    contact_times = []  # contact duration (ms)
    cadence_values = [] # cadence_spm from ESP

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            # CSV header now includes all fields:
            f.write("type,time_ms,foot,fsr_peak,contact_ms,cadence_spm\n")

            while True:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue

                # expect: STEP,time_ms,foot,fsr_peak,contact_ms,cadence_spm
                if not raw.startswith("STEP"):
                    continue

                parts = raw.split(",")
                if len(parts) != 6:
                    print("Skipping malformed line:", raw)
                    continue

                try:
                    time_ms    = int(parts[1])
                    foot       = int(parts[2])
                    fsr_peak   = int(parts[3])
                    contact_ms = int(parts[4])
                    cadence_spm = float(parts[5])
                except ValueError:
                    print("Skipping non-integer/float line:", raw)
                    continue

                if foot not in (1, 2):
                    print("Skipping invalid foot id:", raw)
                    continue
                if not (MIN_FSR <= fsr_peak <= MAX_FSR):
                    print("Skipping out-of-range fsr:", raw)
                    continue

                if t0 is None:
                    t0 = time_ms

                t_sec = (time_ms - t0) / 1000.0

                # log full data to CSV
                f.write(f"STEP,{time_ms},{foot},{fsr_peak},{contact_ms},{cadence_spm}\n")
                f.flush()

                # store for plotting
                times.append(t_sec)
                feet.append(foot)
                fsr_values.append(fsr_peak)
                contact_times.append(contact_ms)
                cadence_values.append(cadence_spm)

    except KeyboardInterrupt:
        print("\n\nSession ended — generating plots...")
    finally:
        ser.close()

    if not times:
        print("No valid STEP data collected. Nothing to plot.")
        return

    # ---- sort by time ----
    combined = sorted(
        zip(times, feet, fsr_values, contact_times, cadence_values),
        key=lambda x: x[0]
    )
    times, feet, fsr_values, contact_times, cadence_values = zip(*combined)

    # split by foot
    t_right = [t for t, ft in zip(times, feet) if ft == 1]
    v_right = [v for v, ft in zip(fsr_values, feet) if ft == 1]

    t_left  = [t for t, ft in zip(times, feet) if ft == 2]
    v_left  = [v for v, ft in zip(fsr_values, feet) if ft == 2]

    # ---- create figure: 2 plots (FSR + cadence) ----
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=False)

    # 1) FSR vs time (lines + markers)
    if t_right:
        ax1.plot(t_right, v_right, "-o", label="Right foot")
    if t_left:
        ax1.plot(t_left, v_left, "-s", label="Left foot")

    ax1.set_title("Step Force Over Time")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("FSR peak value")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    all_t = list(times)
    all_v = list(fsr_values)
    ax1.set_xlim(min(all_t) - 0.2, max(all_t) + 0.2)
    vmin, vmax = min(all_v), max(all_v)
    if vmin == vmax:
        vmin -= 10
        vmax += 10
    pad = 0.05 * (vmax - vmin)
    ax1.set_ylim(vmin - pad, vmax + pad)

    # 2) Cadence vs time using ESP value
    ax2.plot(times, cadence_values, "-")
    ax2.set_title("Cadence (steps per minute, from ESP)")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Steps/min")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(plot_path, dpi=200)
    plt.show()

    print(f"\nPlot saved to: {plot_path}")
    print(f"Data saved to: {log_path}\n")
    print("Done! 🏁")


if __name__ == "__main__":
    main()
