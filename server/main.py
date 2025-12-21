import sys
import serial
import argparse
import threading
from utils.midi_player import MidiBeatSync
from utils.logger import Logger
from utils.BPM_estimation import BPM_estimation
from utils.comms import session_handshake, handle_engine_command, handle_step

#parse the arguments
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
    parser.add_argument(
        "--session-name",
        type=str,
        default=None,
        help="Custom name for the session log directory",
    )
    parser.add_argument(
        "--serial-port",
        type=str,
        default="COM5",
        help="Serial port for the ESP32 (default: COM5)",
    )
    return parser.parse_args()
    
def main(args, status_callback=print, stop_event=None, session_dir_callback=None, command_queue=None):
    midi_path = args.midi_path
    
    # 1. Initialize Logger 
    logger = Logger(gui_callback=status_callback, session_name=getattr(args, 'session_name', None))
    
    # OUTPUT SESSION DIR FOR GUI PARSING
    # The GUI listens for "SESSION_DIR:..." to know where to save the plot.
    print(f"SESSION_DIR:{logger.path}")
    sys.stdout.flush() # Ensure it sends immediately
    


    if session_dir_callback:
        session_dir_callback(logger.path)
        
    # 2. Initialize the midi player  
    logger.log("DEBUG: Attempting to initialize MidiBeatSync...")
    
    try:
        player = MidiBeatSync(midi_path)
        
        logger.log("DEBUG: MidiBeatSync initialized successfully.")
    except Exception as e:
        logger.log(f"CRITICAL ERROR: Failed to initialize MIDI Player: {e}")
        print(f"CRITICAL ERROR: {e}")
        sys.stdout.flush()
        return None, logger, None
    
    # 3. Log Mode
    if args.manual:
        logger.log("Starting in MANUAL MODE.")
        if args.bpm:
            logger.log(f"Setting fixed BPM to {args.bpm}")
            player.set_BPM(args.bpm)
        else:
            logger.log(f"Using default song BPM: {player.songBPM}")
    else:
        logger.log("Starting in DYNAMIC MODE")
    
    # 4. Initialize BPM Estimation
    bpm_estimation = BPM_estimation(player, logger, manual_mode=args.manual, manual_bpm=args.bpm)
    logger.log("Session started")
    
    # 5. Open Serial Port
    port = args.serial_port
    ser = None
    logger.log(f"DEBUG: Attempting to open serial port {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=0.2)
        logger.log(f"DEBUG: Serial port {port} opened successfully.")
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
    
    # start playback after handshake (threaded player handles timing)
    player.start()
    logger.log("Running main loop...")
    
    # ------------------------------------------------------------------
    # STDIN LISTENER (For Subprocess Mode)
    # If no external queue is provided, we create one and listen to STDIN.
    # ------------------------------------------------------------------
    if command_queue is None:
        from queue import SimpleQueue
        
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
            
            quit =handle_engine_command(cmd, ser, logger, bpm_estimation, player)
            if quit:
                stop_event = threading.Event()
                stop_event.set()
                break
          
        # ANIMATION: We must run update_bpm() every loop iteration.
        if not args.manual:
            bpm_estimation.update_bpm()
            
        # read the step from the serial port
        raw_line = ser.readline()
        if not raw_line:
            continue
        # handle the step
        try:
            bpm, instant_bpm, current_ts = handle_step(raw_line, player.walkingBPM)
        except ValueError:
            continue
        
        #register the step and log the data
        bpm_estimation.register_step(bpm)    
        logger.log_data(current_ts, player.walkingBPM, bpm, step_event=True)
        logger.log(f"Processed: BPM={bpm}")
        
    logger.log("Session ended")
    player.stop()
    player.close()
    if ser: ser.close()
    print("EXIT_CLEAN")
    return player, logger, bpm_estimation

if __name__ == "__main__":
    main(parse_args())