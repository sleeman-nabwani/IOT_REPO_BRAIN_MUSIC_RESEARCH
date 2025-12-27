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
import os
import json
import traceback
from utils.midi_player import MidiBeatSync
from utils.logger import Logger
from utils.BPM_estimation import BPM_estimation
from utils.comms import session_handshake, handle_engine_command, handle_step
from utils.main_helper_functions import retrain_prediction_model
from utils.LGBM_predictor import LGBMPredictor
# from utils.safety import safe_execute

# region agent log
_DEBUG_LOG_PATH = r"c:\Users\sleem\Desktop\Technion\semester_9\IOT\IOT_REPO_BRAIN_MUSIC_RESEARCH\.cursor\debug.log"
def _dbg(runId: str, hypothesisId: str, location: str, message: str, data: dict | None = None):
    payload = {
        "sessionId": "debug-session",
        "runId": runId,
        "hypothesisId": hypothesisId,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion

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
        "--disable-prediction-model",
        "--disable-prediction",
        dest="disable_prediction",
        action="store_true",
        help="Disable prediction model for this run",
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
    # region agent log
    run_id = os.getenv("DBG_RUN_ID") or f"engine_{int(time.time() * 1000)}"
    _dbg(
        run_id,
        "M",
        "server/main.py:main",
        "Engine starting",
        {"midi_path": midi_path, "serial_port": getattr(args, "serial_port", None), "manual": bool(getattr(args, "manual", False))},
    )
    # endregion
    
    # 1. Initialize Logger 
    logger = Logger(gui_callback=status_callback, session_name=getattr(args, 'session_name', None))
    
    # OUTPUT SESSION DIR FOR GUI PARSING
    # The GUI listens for "SESSION_DIR:..." to know where to save the plot.
    print(f"SESSION_DIR:{logger.path}")
    sys.stdout.flush() # Ensure it sends immediately
    # region agent log
    _dbg(run_id, "M", "server/main.py:main", "SESSION_DIR printed", {"path": str(logger.path)})
    # endregion
    


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
    else:
        logger.log("Starting in DYNAMIC MODE")
    
    # 4. Initialize prediction model (currently KNN predictor)
    if args.disable_prediction:
        prediction_model = None
        logger.log("Prediction model disabled")
    else:
        prediction_model = LGBMPredictor()
        logger.log("Prediction model enabled (LightGBM)")
    
    # 5. Initialize BPM Estimation
    bpm_estimation = BPM_estimation(
        player,
        logger,
        manual_mode=args.manual,
        manual_bpm=args.bpm,
        knn_predictor=prediction_model,
    )
    logger.log("Session started")
    
    # 6. Open Serial Port
    port = args.serial_port
    ser = None
    logger.log(f"DEBUG: Attempting to open serial port {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=0.2)
        logger.log(f"DEBUG: Serial port {port} opened successfully.")
        # region agent log
        _dbg(run_id, "S", "server/main.py:main", "Serial opened", {"port": port, "timeout": ser.timeout})
        # endregion
    except Exception as e:
        logger.log(f"Failed to open serial port {port}: {e}")
        # region agent log
        _dbg(run_id, "S", "server/main.py:main", "Serial open failed", {"port": port, "error": repr(e), "traceback": traceback.format_exc()[-1500:]})
        # endregion
        return player, logger, bpm_estimation

    # Config from arguments
    smoothing_window = getattr(args, 'smoothing', 3)
    stride = getattr(args, 'stride', 1)

    if not session_handshake(ser, logger, smoothing_window=smoothing_window, stride=stride):
        logger.log("Handshake failed; aborting session")
        # region agent log
        _dbg(run_id, "S", "server/main.py:main", "Handshake failed", {})
        # endregion
        return player, logger, bpm_estimation

    # region agent log
    _dbg(run_id, "S", "server/main.py:main", "Handshake completed", {"smoothing_window": smoothing_window, "stride": stride})
    # endregion

    # runtime serial reads should be non-blocking to avoid slowing playback
    ser.timeout = 0
    
    # start playback after handshake (threaded player handles timing)
    player.start()
    logger.log("Running main loop...")

    # region agent log
    def _hb():
        for i in range(6):  # 12 seconds
            _dbg(run_id, "H", "server/main.py:heartbeat", "Engine heartbeat", {"i": i})
            time.sleep(2)
    threading.Thread(target=_hb, daemon=True).start()
    # endregion
    
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
    # region agent log
    loop_last_log = time.time()
    loops = 0
    empty_reads = 0
    parse_fail = 0
    steps_ok = 0
    last_nonempty_ts = time.time()
    first_steps_logged = 0
    first_fail_logged = 0
    # endregion
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
            # region agent log
            empty_reads += 1
            loops += 1
            # endregion
            continue

        # region agent log
        loops += 1
        last_nonempty_ts = time.time()
        # endregion
        # handle the step
        try:
            bpm, instant_bpm, current_ts = handle_step(raw_line, player.walkingBPM)
        except ValueError:
            # region agent log
            parse_fail += 1
            if first_fail_logged < 3:
                first_fail_logged += 1
                _dbg(
                    run_id,
                    "S",
                    "server/main.py:main",
                    "handle_step parse failed",
                    {"n": first_fail_logged, "raw": raw_line[:200].decode("utf-8", errors="ignore")},
                )
            # endregion
            continue
        
        #register the step and log the data
        bpm_estimation.register_step(bpm)    
        logger.log_data(current_ts, player.walkingBPM, bpm, step_event=True)
        logger.log(f"Processed: BPM={bpm}")

        # region agent log
        steps_ok += 1
        if first_steps_logged < 3:
            first_steps_logged += 1
            _dbg(
                run_id,
                "S",
                "server/main.py:main",
                "Step processed",
                {"n": first_steps_logged, "bpm": bpm, "instant_bpm": instant_bpm, "song_bpm": player.walkingBPM},
            )
        # endregion
        
        # CPU Yield (Prevent 100% core usage)
        time.sleep(0.001)

        # region agent log
        now = time.time()
        if now - loop_last_log >= 1.0 and now - (loop_last_log) < 10.0 + 1.0:
            _dbg(
                run_id,
                "S",
                "server/main.py:main",
                "Loop stats (1s)",
                {
                    "loops": loops,
                    "empty_reads": empty_reads,
                    "parse_fail": parse_fail,
                    "steps_ok": steps_ok,
                    "since_nonempty_s": now - last_nonempty_ts,
                },
            )
            loops = 0
            empty_reads = 0
            parse_fail = 0
            steps_ok = 0
            loop_last_log = now
        # endregion
        
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