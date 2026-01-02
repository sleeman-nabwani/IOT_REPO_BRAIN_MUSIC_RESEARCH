"""
Brain-Music Sync - Main Engine

This module orchestrates the real-time BPM synchronization loop:
1. Connects to ESP32 sensor via serial
2. Reads step data and calculates walking tempo
3. Adjusts MIDI playback speed to match user's pace
4. Logs session data for analysis

Usage:
    python main.py [midi_path] [--manual] [--bpm N] [--serial-port COMX]
"""
import sys
import time
import serial
import argparse
import threading
from utils.midi_player import MidiBeatSync
from utils.logger import Logger
from utils.BPM_estimation import BPM_estimation
from utils.comms import session_handshake, handle_engine_command, handle_step
from utils.main_helper_functions import retrain_prediction_model
from utils.LGBM_predictor import LGBMPredictor
# from utils.safety import safe_execute

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
        default="COM3",
        help="Serial port for the ESP32 (default: COM3)",
    )
    parser.add_argument(
        "--alpha-up",
        type=float,
        default=None,
        help="Optional attack smoothing alpha override",
    )
    parser.add_argument(
        "--alpha-down",
        type=float,
        default=None,
        help="Optional decay smoothing alpha override",
    )
    parser.add_argument(
        "--disable-prediction-model",
        "--disable-prediction",
        dest="disable_prediction",
        action="store_true",
        help="Disable prediction model for this run",
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Enable hybrid mode (starts dynamic, locks if steady)",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Enable Random Drift Mode",
    )
    parser.add_argument(
        "--random-span",
        type=float,
        default=0.20,
        help="Difficulty span for Random Mode (0.0-0.5)",
    )
    return parser.parse_args()

def start_stdin_listener(command_queue):
    """
    Reads from stdin in a separate thread and puts lines into the command queue.
    Needed for SubprocessManager communication.
    """
    import threading
    import sys
    
    def _listen():
        for line in sys.stdin:
            command_queue.put(line.strip())
    
    t = threading.Thread(target=_listen, daemon=True)
    t.start()

def main(args, status_callback=print, stop_event=None, session_dir_callback=None, command_queue=None):
    midi_path = args.midi_path
    smoothing_window = getattr(args, 'smoothing', 3)
    stride = getattr(args, 'stride', 1)
    
    if args.manual:
        run_type = "manual"
    elif getattr(args, "hybrid", False):
        run_type = "hybrid"
    elif getattr(args, "random", False):
        run_type = "random"
    else:
        run_type = "dynamic"

    # 1. Initialize Logger 
    logger = Logger(
        gui_callback=status_callback,
        session_name=getattr(args, 'session_name', None),
        smoothing_window=smoothing_window,
        stride=stride,
        run_type=run_type,
    )
    
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
    
    # Seed initial GUI data so song BPM appears immediately
    try:
        logger.log_data(time.time(), player.walkingBPM, player.walkingBPM, step_event=False)
    except Exception:
        pass
    
    # 3. Log Mode
    if args.manual:
        logger.log("Starting in MANUAL MODE.")
        if args.bpm:
            logger.log(f"Setting fixed BPM to {args.bpm}")
            player.set_BPM(args.bpm)
        else:
            logger.log(f"Using default song BPM: {player.songBPM}")
    elif getattr(args, "random", False):
        logger.log("Starting in RANDOM DRIFT MODE.")
    else:
        logger.log("Starting in DYNAMIC MODE")
    logger.log(f"Run type: {run_type}")
    
    # 4. Initialize prediction model (currently LightGBM predictor)
    if args.disable_prediction:
        prediction_model = None
        logger.log("Prediction model disabled")
    else:
        prediction_model = LGBMPredictor(run_type=run_type)
        logger.log("Prediction model enabled (LightGBM)")
    
    # 5. Initialize BPM Estimation
    bpm_estimation = BPM_estimation(
        player,
        logger,
        manual_mode=args.manual,
        manual_bpm=args.bpm,
        prediction_model=prediction_model,
        smoothing_window=smoothing_window,
        stride=stride,
        run_type=run_type,
        hybrid_mode=getattr(args, 'hybrid', False),
    )

    if getattr(args, "random", False):
        if hasattr(bpm_estimation, 'set_random_mode'):
             bpm_estimation.set_random_mode(True, span=getattr(args, 'random_span', 0.20))
    if args.alpha_up is not None:
        bpm_estimation.set_smoothing_alpha_up(args.alpha_up)
    if args.alpha_down is not None:
        bpm_estimation.set_smoothing_alpha_down(args.alpha_down)
    logger.log("Session started")
    
    # 6. Open Serial Port
    port = args.serial_port
    ser = None
    logger.log(f"DEBUG: Attempting to open serial port {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=0.2)
        logger.log(f"DEBUG: Serial port {port} opened successfully.")
    except Exception as e:
        logger.log(f"Failed to open serial port {port}: {e}")
        return player, logger, bpm_estimation

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
        
        start_stdin_listener(command_queue)
    
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
        
        # ANIMATION: Run update_bpm() every loop iteration (manual or dynamic).
        # In manual mode this still emits log packets each loop for plotting.
        bpm_estimation.update_bpm()
            
        # read the step from the serial port
        raw_line = ser.readline()
        if not raw_line:
            time.sleep(0.001)  # yield even when idle to avoid CPU/GIL starvation
            continue

        # handle the step
        # TWEAK: Check for BUTTON messages first (BTN,<delta>)
        try:
            line_str = raw_line.decode("utf-8", errors="ignore").strip()
            if line_str.startswith("BTN,"):
                parts = line_str.split(",")
                if len(parts) >= 2:
                    delta = float(parts[1])
                    logger.log(f"HARDWARE: Button Delta Received: {delta}")
                    
                    # Refactored to BPM_estimation
                    bpm_estimation.register_button_delta(delta)
                continue

            bpm, instant_bpm, sensor_ts, foot = handle_step(raw_line, player.walkingBPM)
        except ValueError:
            time.sleep(0.001)
            continue

        # Log using wall-clock processing time to keep CSV strictly monotonic.
        event_epoch = time.time()
        
        # register the step and log the data
        bpm_estimation.register_step(bpm, instant_bpm)
        logger.log_data(event_epoch, player.walkingBPM, bpm, step_event=True, instant_bpm=instant_bpm)
        logger.log(f"Processed: BPM={bpm}")

        # CPU Yield (Prevent 100% core usage)
        time.sleep(0.001)
        
    logger.log("Session ended")
    player.stop()
    player.close()
    if ser: ser.close()
    
    # Auto-retrain prediction model with new session data
    retrain_prediction_model()
    
    print("EXIT_CLEAN")
    return player, logger, bpm_estimation

if __name__ == "__main__":
    main(parse_args())