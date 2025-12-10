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
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Enable manual tempo mode (music tempo will not change based on steps)",
    )
    parser.add_argument(
        "--bpm",
        type=float,
        help="Set a fixed BPM for manual mode (optional, defaults to song BPM)",
    )
    return parser.parse_args()

def main(args):
    midi_path = args.midi_path
    # initializing the midi player  
    player = MidiBeatSync(midi_path)
    
    if args.manual:
        print(f"Starting in MANUAL MODE.")
        if args.bpm:
            print(f"Setting fixed BPM to {args.bpm}")
            player.set_BPM(args.bpm)
        else:
             print(f"Using default song BPM: {player.songBPM}")
    else:
        print(f"Starting in DYNAMIC MODE")

    playback = player.play()
    
    # initializing the logger
    logger = Logger()
    bpm_estimation = BPM_estimation(player, logger, manual_mode=args.manual, manual_bpm=args.bpm)
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


        # Check for manual updates from GUI / I assumed that we will get the bpm from the gui directly into the constructor in the BPM_estimation file
        new_manual_bpm = bpm_estimation.check_manual_bpm_update()
        if new_manual_bpm is not None:
             print(f"Applying manual BPM change to: {new_manual_bpm}")
             player.set_BPM(new_manual_bpm)
             logger.log(f"Manual BPM updated to {new_manual_bpm}")
            
        raw_line = ser.readline()
        if not raw_line:
            if not args.manual:
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
        
        if not args.manual:
            player.set_BPM(bpm)
            
        logger.log(f"Step received: {step}")
    logger.log("Session ended")
    player.close()
if __name__ == "__main__":
    main(parse_args())
