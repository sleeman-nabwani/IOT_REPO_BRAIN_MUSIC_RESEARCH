from midi_player import MidiBeatSync
import time
import serial
import argparse
from logger import Logger
from BPM_estimation import BPM_estimation
from comms import session_handshake

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
    parser.add_argument(
        "--smoothing",
        type=int,
        default=3,
        help="Set the smoothing window size (number of steps to average)",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Set the BPM update stride (update BPM every N steps)",
    )
    return parser.parse_args()
    
def main(args, status_callback=print, stop_event=None, session_dir_callback=None, command_queue=None):
    midi_path = args.midi_path
    
    # 1. Initialize Logger FIRST so we can log init steps
    logger = Logger(gui_callback=status_callback)
    
    # OUTPUT SESSION DIR FOR GUI PARSING
    # The GUI listens for "SESSION_DIR:..." to know where to look for CSVs.
    print(f"SESSION_DIR:{logger.path}")
    sys.stdout.flush() # Ensure it sends immediately

    if session_dir_callback:
        session_dir_callback(logger.path)

    # 2. Initialize the midi player  
    player = MidiBeatSync(midi_path)
    
    # 3. Log Mode
    if args.manual:
        logger.log(f"Starting in MANUAL MODE.")
        if args.bpm:
            logger.log(f"Setting fixed BPM to {args.bpm}")
            player.set_BPM(args.bpm)
        else:
             logger.log(f"Using default song BPM: {player.songBPM}")
    else:
        logger.log(f"Starting in DYNAMIC MODE")

    playback = player.play()
    
    # 4. Initialize BPM Estimation
    bpm_estimation = BPM_estimation(player, logger, manual_mode=args.manual, manual_bpm=args.bpm)
    logger.log("Session started")
    
    # 5. Open Serial Port
    port = getattr(args, 'serial_port', "COM5")
    ser = None
    try:
        ser = serial.Serial(port, 115200, timeout=0.2)
    except Exception as e:
        logger.log(f"Failed to open serial port {port}: {e}")
        return player, logger, bpm_estimation

    # Config from arguments
    smoothing_window = getattr(args, 'smoothing_window', 3)
    stride = getattr(args, 'stride', 1)

    if not session_handshake(ser, logger, smoothing_window=smoothing_window, stride=stride):
        logger.log("Handshake failed; aborting session")
        return player, logger, bpm_estimation

    # runtime serial reads should be non-blocking to avoid slowing playback
    ser.timeout = 0
    
    # Restart playback after handshake (optional reset)
    playback = player.play()
    logger.log("Running main loop...")
    
    # ------------------------------------------------------------------
    # STDIN LISTENER (For Subprocess Mode)
    # If no external queue is provided, we create one and listen to STDIN.
    # ------------------------------------------------------------------
    if command_queue is None:
        import sys
        from queue import SimpleQueue
        import threading
        
        command_queue = SimpleQueue()
        
        def stdin_listener():
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line: break
                    line = line.strip()
                    if line: command_queue.put(line)
                except: break
        
        worker_thread = threading.Thread(target=stdin_listener, daemon=True)
        worker_thread.start()
    
    # ==================================================================================
    # MAIN LOOP
    # ==================================================================================
    while True:
        # CHECK STOP EVENT
        if stop_event and stop_event.is_set():
            logger.log("Session stopped by user.")
            break
            
        # PROCESS COMMAND QUEUE (From GUI Pipe or Thread)
        while not command_queue.empty():
            cmd = command_queue.get_nowait()
            
            # 1. Tuple Command (from Threading Mode)
            if isinstance(cmd, tuple): 
                # e.g. ("window", 10)
                ctype, cval = cmd
                if ctype == "window":
                    send_config_command(ser, logger, "SET_WINDOW", cval, "steps window", "ACK,WINDOW")
                elif ctype == "stride":
                    send_config_command(ser, logger, "SET_STRIDE", cval, "update stride", "ACK,STRIDE")
                    
            # 2. String Command (from STDIN/Subprocess Mode)
            elif isinstance(cmd, str):
                # Format: "CMD:VALUE"
                if ":" in cmd:
                    parts = cmd.split(":")
                    key = parts[0].upper()
                    val = parts[1]
                    
                    try:
                        if key == "SET_ALPHA_UP":
                            bpm_estimation.set_smoothing_alpha_up(float(val))
                            logger.log(f"Config: Alpha UP set to {val}")
                        elif key == "SET_ALPHA_DOWN":
                            bpm_estimation.set_smoothing_alpha_down(float(val))
                            logger.log(f"Config: Alpha DOWN set to {val}")
                        elif key == "SET_MANUAL_BPM":
                            player.set_BPM(float(val))
                            logger.log(f"Config: Manual BPM set to {val}")
                        elif key == "SET_WINDOW":
                            send_config_command(ser, logger, "SET_WINDOW", int(val), "steps window", "ACK,WINDOW")
                        elif key == "SET_STRIDE":
                             send_config_command(ser, logger, "SET_STRIDE", int(val), "update stride", "ACK,STRIDE")
                    except ValueError:
                        logger.log(f"Invalid command format: {cmd}")
                
                elif cmd == "QUIT":
                    stop_event = threading.Event()
                    stop_event.set()
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
             player.set_BPM(new_manual_bpm)
             logger.log(f"Manual BPM updated to {new_manual_bpm}")
            
        # ANIMATION: We must run update_bpm() every loop iteration.
        if not args.manual:
            bpm_estimation.update_bpm()
            
        raw_line = ser.readline()
        if not raw_line:
            continue
        
        step = raw_line.decode("utf-8", errors="ignore").strip()
        logger.log(f"Step received: {step}")
        try:
            ts_str, foot_str, interval_str, bpm_str = step.split(",")

            ts = int(ts_str)
            foot = int(foot_str)
            interval = int(float(interval_str))
            bpm = float(bpm_str)

            # FILTER: Ignore startup/pause spikes
            if interval > 3000:
                logger.log(f"Ignoring long interval: {interval}ms")
                continue

            if interval == 0 and bpm == 0.0:
                bpm = player.walkingBPM

            # LOGGING: Record the "Dot" event (Raw Step) for the graph.
            current_ts = time.time()
            # Register the step as a new TARGET for smoothing
            bpm_estimation.register_step(bpm)
            
            logger.log_csv(current_ts, player.walkingBPM, bpm, step_event=True)
            logger.log(f"Processed: Interval={interval}, BPM={bpm}")

        except ValueError:
            continue
        
    logger.log("Session ended")
    player.close()
    if ser: ser.close()
    print("EXIT_CLEAN") # Signal to GUI
    return player, logger, bpm_estimation

if __name__ == "__main__":
    main(parse_args())