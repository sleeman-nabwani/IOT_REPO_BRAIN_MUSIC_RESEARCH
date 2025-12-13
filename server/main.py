from midi_player import MidiBeatSync
import time
import serial
import argparse
from logger import Logger
from BPM_estimation import BPM_estimation

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Brain-music demo player")
    # TWEAK: Change the default MIDI file here if you want a different song by default.
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
  
def main(args, status_callback=print, stop_event=None, session_dir_callback=None):
    midi_path = args.midi_path
    
    # Callback wrapper to handle both print and GUI logging
    def log(msg):
        if status_callback: status_callback(msg)

    # initializing the midi player  
    player = MidiBeatSync(midi_path)
    
    #checking if in manual mode:
    if args.manual:
        log(f"Starting in MANUAL MODE.")
        if args.bpm:
            log(f"Setting fixed BPM to {args.bpm}")
            player.set_BPM(args.bpm)
        else:
             log(f"Using default song BPM: {player.songBPM}")
    else:
        log(f"Starting in DYNAMIC MODE")

    playback = player.play()
    
    # initializing the logger:
    logger = Logger()
    if session_dir_callback:
        session_dir_callback(logger.path)
        
    #initializing the bpm estimation:
    bpm_estimation = BPM_estimation(player, logger, manual_mode=args.manual, manual_bpm=args.bpm)
    logger.log("Session started")
    
    #opening the serial port for communication with the ESP32
    # Use args.serial_port if available, else default
    port = getattr(args, 'serial_port', "COM3")
    
    ser = None
    try:
        ser = serial.Serial(port, 115200, timeout=0.2)
    except Exception as e:
        log(f"Failed to open serial port {port}: {e}")
        return player, logger, bpm_estimation

    if not session_handshake(ser, logger):
        logger.log("Handshake failed; aborting session")
        log("Handshake failed.")
        return player, logger, bpm_estimation

    # runtime serial reads should be non-blocking to avoid slowing playback
    ser.timeout = 0
    
    #starting the playback
    playback = player.play()
    log("Session running...")
    
    # ==================================================================================
    # MAIN LOOP
    # This loop runs as fast as possible to:
    # 1. Play the next note in the MIDI file.
    # 2. Check for manual BPM changes (from GUI).
    # 3. Read step data from the Serial Port.
    # 4. Adjust the song tempo if needed.
    # ==================================================================================
    while True:
        # CHECK STOP EVENT
        if stop_event and stop_event.is_set():
            logger.log("Session stopped by user.")
            break

        try:
            next(playback)
        except StopIteration:
            logger.log("Song finished. Restarting...")
            playback = player.play()
            continue


        # Check for manual updates from GUI
        new_manual_bpm = bpm_estimation.check_manual_bpm_update()
        if new_manual_bpm is not None:
             log(f"Applying manual BPM change to: {new_manual_bpm}")
             player.set_BPM(new_manual_bpm)
             logger.log(f"Manual BPM updated to {new_manual_bpm}")
            
        raw_line = ser.readline()
        if not raw_line:
            if not args.manual:
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
        
        if not args.manual:
            player.set_BPM(bpm)
            
        logger.log("Step has been processed")
    
    logger.log("Session ended")
    player.close()
    if ser: ser.close()
    return player, logger, bpm_estimation

if __name__ == "__main__":
    main(parse_args())