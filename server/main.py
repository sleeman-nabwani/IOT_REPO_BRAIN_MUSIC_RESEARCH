from midi_player import MidiBeatSync
import time
import serial
import argparse
from logger import Logger

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Brain-music demo player")
    parser.add_argument(
        "midi_path",
        nargs="?",
        default=None,
        help="Path to the MIDI file to play",
    )
    return parser.parse_args()


def main(midi_path:str):
    # initializing the midi player
    player = MidiBeatSync(midi_path)
    playback = player.play()
    
    # initializing the logger
    logger = Logger()
    logger.log(f"Session started at {time.time()}")
    #opening the serial port for communication with the ESP32
    ser = serial.Serial("COM3", 115200, timeout=0.01)
    logger.log(f"Serial port opened at {time.time()} on port{ser.port}, baud {ser.baudrate}")

    while True:
        try:
            next(playback)  # play one MIDI event
        except StopIteration:
            logger.log(f"Song finished at {time.time()}. Restarting...")
            playback = player.play()
            continue
        logger.log(f"MIDI event played at {time.time()}")
        
        raw_line = ser.readline()
        if not raw_line:
            continue
        
        step = raw_line.decode("utf-8", errors="ignore").strip()
        try:
            ts_str, foot_str, interval_str, bpm_str = step.split(",")

            ts = int(ts_str)
            foot = int(foot_str)
            interval = int(interval_str)
            bpm = float(bpm_str)

            # use it:
            player.set_BPM(bpm)
            logger.log(f"{ts}, {foot}, {interval}, {bpm}")

        except ValueError:
            continue

        logger.log_csv(time.time(), player.songBPM, bpm)
        logger.log(f"Step received at {time.time()}: {step}")
    logger.log(f"Session ended at {time.time()}")
    player.close()
if __name__ == "__main__":
    main(parse_args().midi_path)
