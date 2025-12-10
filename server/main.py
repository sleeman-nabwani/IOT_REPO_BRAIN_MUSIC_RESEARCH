from midi_player import MidiBeatSync
import time
import serial
import argparse
from logger import Logger
from BPM_estimation import BPM_estimation

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Brain-music demo player")
    parser.add_argument(
        "midi_path",
        nargs="?",
        default="midi_files\Technion_March1.mid",
        help="Path to the MIDI file to play",
    )
    return parser.parse_args()

def session_handshake(ser: serial.Serial, logger: Logger) -> bool:
    """Perform RESET/START handshake with bounded retries."""
    # allow the ESP to finish boot messages, then clear the buffer
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

def main(midi_path:str):
    # initializing the midi player
    player = MidiBeatSync(midi_path)
    # initializing the logger
    logger = Logger()
    #initializing the bpm estimation
    bpm_estimation = BPM_estimation(player, logger)
    logger.log("Session started")
    #opening the serial port for communication with the ESP32
    ser = serial.Serial("COM3", 115200, timeout=0.2)
    if not session_handshake(ser, logger):
        logger.log("Handshake failed; aborting session")
        return
    # runtime serial reads should be non-blocking to avoid slowing playback
    ser.timeout = 0
    
    #starting the playback
    playback = player.play()
    #main loop
    while True:
        try:
            next(playback)
        except StopIteration:
            logger.log("Song finished. Restarting...")
            playback = player.play()
            continue
        
        raw_line = ser.readline()
        if not raw_line:
            bpm_estimation.update_bpm()
            continue
        
        step = raw_line.decode("utf-8", errors="ignore").strip()
        logger.log(f"Step received: {step}")
        try:
            ts_str, foot_str, interval_str, bpm_str = step.split(",")

            ts = int(ts_str)
            foot = int(foot_str)
            interval = int(interval_str)
            bpm = float(bpm_str)

            # If the first step arrives with zeroed timing/BPM, assume current song tempo
            if interval == 0 and bpm == 0.0:
                bpm = player.walkingBPM
                interval = int(60000 / bpm) if bpm > 0 else 0

            # use it:
            logger.log(f"{ts}, {foot}, {interval}, {bpm}")

        except ValueError:
            bpm_estimation.update_bpm()
            continue
        
        current_ts = time.time()
        bpm_estimation.update_recorded_values(current_ts, bpm)
        logger.log_csv(current_ts, player.walkingBPM, bpm, step_event=True)
        player.set_BPM(bpm)
        logger.log("Step has been processed")
    logger.log("Session ended")
    player.close()
if __name__ == "__main__":
    main(parse_args().midi_path)
