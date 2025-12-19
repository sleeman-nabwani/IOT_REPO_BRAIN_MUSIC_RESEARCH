import time
import serial

from midi_player import MidiBeatSync
from logger import Logger
from BPM_estimation import BPM_estimation


def session_handshake(ser: serial.Serial, logger: Logger) -> bool:
    """Perform RESET/START handshake with bounded retries."""
    time.sleep(0.5)
    ser.reset_input_buffer()

    for _ in range(5):
        ser.write(b"RESET\n")
        time.sleep(0.1)
        resp = ser.readline()
        decoded = resp.decode("utf-8", errors="ignore").strip() if resp else ""
        if decoded == "ACK,RESET":
            logger.log("Reset ACK received")
            break
        logger.log(f"Unexpected or no ACK to RESET (got: {decoded!r}), retrying...")
    else:
        logger.log("RESET handshake failed")
        return False

    for _ in range(5):
        ser.write(b"START\n")
        time.sleep(0.1)
        resp = ser.readline()
        decoded = resp.decode("utf-8", errors="ignore").strip() if resp else ""
        if decoded == "ACK,START":
            logger.log("Start ACK received")
            logger.log("Session handshake completed")
            return True
        logger.log(f"Unexpected or no ACK to START (got: {decoded!r}), retrying...")

    logger.log("START handshake failed")
    return False


def create_session(
    midi_path: str,
    manual_mode: bool,
    manual_bpm: float | None,
    status_callback=None,
    session_dir_callback=None,
):
    """Build player/logger/BPM estimation and report the session folder."""
    player = MidiBeatSync(midi_path)
    logger = Logger()
    if session_dir_callback:
        session_dir_callback(logger.path)
    bpm_est = BPM_estimation(player, logger, manual_mode=manual_mode, manual_bpm=manual_bpm)

    if status_callback:
        mode_msg = "Manual mode" if manual_mode else "Dynamic mode"
        bpm_msg = f", fixed BPM {manual_bpm}" if manual_bpm else ""
        status_callback(f"Session init: {mode_msg}{bpm_msg}")
    return player, logger, bpm_est


def run_session_loop(
    player: MidiBeatSync,
    logger: Logger,
    bpm_est: BPM_estimation,
    serial_port: str = "COM3",
    status_callback=None,
    stop_event=None,
):
    """Drive playback + serial loop. Blocks until stop_event is set (if provided)."""
    ser = None
    try:
        try:
            ser = serial.Serial(serial_port, 115200, timeout=0.2)
        except Exception as exc:
            if status_callback:
                status_callback(f"Could not open serial port {serial_port}: {exc}")
            return

        if not session_handshake(ser, logger):
            if status_callback:
                status_callback("Handshake failed; stopping session.")
            return
        ser.timeout = 0

        playback = player.play()
        if status_callback:
            status_callback("Session running.")

        while not (stop_event and stop_event.is_set()):
            try:
                next(playback)
            except StopIteration:
                logger.log("Song finished. Restarting...")
                playback = player.play()
                continue

            new_manual_bpm = bpm_est.check_manual_bpm_update()
            if new_manual_bpm is not None:
                if status_callback:
                    status_callback(f"Applying manual BPM: {new_manual_bpm}")
                player.set_BPM(new_manual_bpm)
                logger.log(f"Manual BPM updated to {new_manual_bpm}")

            raw_line = ser.readline()
            if not raw_line:
                if not bpm_est.manual_mode:
                    bpm_est.update_bpm()
                continue

            step = raw_line.decode("utf-8", errors="ignore").strip()
            logger.log(f"Step received: {step}")
            try:
                ts_str, foot_str, interval_str, bpm_str = step.split(",")

                ts = int(ts_str)
                foot = int(foot_str)
                interval = int(interval_str)
                bpm = float(bpm_str)

                if interval == 0 and bpm == 0.0:
                    bpm = player.walkingBPM
                    interval = int(60000 / bpm) if bpm > 0 else 0

                logger.log(f"{ts}, {foot}, {interval}, {bpm}")

            except ValueError:
                bpm_est.update_bpm()
                continue

            current_ts = time.time()
            bpm_est.update_recorded_values(current_ts, bpm)
            logger.log_csv(current_ts, player.walkingBPM, bpm, step_event=True)

            if not bpm_est.manual_mode:
                player.set_BPM(bpm)

            logger.log("Step has been processed")

            if stop_event and stop_event.is_set():
                break

    finally:
        try:
            if ser:
                ser.close()
        except Exception:
            pass
        try:
            player.close()
        except Exception:
            pass
        if status_callback:
            status_callback("Session ended.")
