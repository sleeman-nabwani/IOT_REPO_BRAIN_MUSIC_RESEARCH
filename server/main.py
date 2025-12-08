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

def main(midi_path:str):
    # initializing the midi player
    player = MidiBeatSync(midi_path)
    playback = player.play()
    
    # initializing the logger
    logger = Logger()
    bpm_estimation = BPM_estimation(player, logger)
    logger.log("Session started")
    #opening the serial port for communication with the ESP32
    ser = serial.Serial("COM3", 115200, timeout=0.01)
    logger.log(f"Serial port opened on port {ser.port}, baud {ser.baudrate}")

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
        try:
            ts_str, foot_str, interval_str, bpm_str = step.split(",")

            ts = int(ts_str)
            foot = int(foot_str)
            interval = int(interval_str)
            bpm = float(bpm_str)

            # use it:
            logger.log(f"{ts}, {foot}, {interval}, {bpm}")

        except ValueError:
            bpm_estimation.update_bpm()
            continue
        
        current_ts = time.time()
        bpm_estimation.update_recorded_values(current_ts, bpm)
        logger.log_csv(current_ts, player.walkingBPM, bpm, step_event=True)
        player.set_BPM(bpm)
        logger.log(f"Step received: {step}")
    logger.log("Session ended")
    player.close()
if __name__ == "__main__":
    main(parse_args().midi_path)
