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
import os
from utils.midi_player import MidiBeatSync
import time
import serial
import argparse
import threading
from utils.logger import Logger
from utils.BPM_estimation import BPM_estimation
from utils.comms import session_handshake, send_config_command, process_input_commands, read_all_sensor_steps, start_stdin_listener
from utils.main_helper_functions import retrain_knn_model

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
    
    # 1. Initialize Logger FIRST so we can log init steps
    logger = Logger(gui_callback=status_callback, session_name=getattr(args, 'session_name', None))
    
    # OUTPUT SESSION DIR FOR GUI PARSING
    # The GUI listens for "SESSION_DIR:..." to know where to look for CSVs.
    print(f"SESSION_DIR:{logger.path}")
    sys.stdout.flush() # Ensure it sends immediately
    


    if session_dir_callback:
        session_dir_callback(logger.path)

    # 2. Initialize the midi player  
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
        logger.log(f"Starting in MANUAL MODE.")
        if args.bpm:
            logger.log(f"Setting fixed BPM to {args.bpm}")
            player.set_BPM(args.bpm)
        else:
             logger.log(f"Using default song BPM: {player.songBPM}")
    else:
        logger.log(f"Starting in DYNAMIC MODE")

    logger.log("DEBUG: Attempting to start playback...")
    playback = player.play()
    logger.log("DEBUG: Playback started.")
    
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
    
    # Restart playback after handshake (optional reset)
    playback = player.play()
    logger.log("Running main loop...")
    
    # ------------------------------------------------------------------
    # STDIN LISTENER (For Subprocess Mode)
    # If no external queue is provided, we create one and listen to STDIN.
    # ------------------------------------------------------------------
    if command_queue is None:
        # sys, SimpleQueue, threading already imported globally or available
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
            
        # PROCESS COMMAND QUEUE (Helper Function)
        process_input_commands(command_queue, ser, logger, bpm_estimation, player, stop_event)
        if stop_event and stop_event.is_set():
             break

        try:
            next(playback)
        except StopIteration:
            logger.log("Song finished. Restarting...")
            playback = player.play()
            continue

        # ANIMATION: We must run update_bpm() every loop iteration.
        # This now also handles any pending manual BPM updates internally.
        if not args.manual:
            bpm_estimation.update_bpm()
            
        # SENSOR READ: Drain the buffer to prevent lag/spikes
        valid_step = read_all_sensor_steps(ser, logger)
        if valid_step is None:
             continue
             
        ts, foot, instant_bpm, avg_bpm = valid_step

        if instant_bpm == 0 and avg_bpm == 0.0:
            avg_bpm = player.walkingBPM

        # LOGGING: Record the "Dot" event (Raw Step) for the graph.
        current_ts = time.time()
        # Register the step as a new TARGET for smoothing (use averaged BPM from ESP32)
        bpm_estimation.register_step(avg_bpm)
        
        logger.log_data(current_ts, player.walkingBPM, avg_bpm, step_event=True)
        logger.log(f"Processed: Instant={instant_bpm:.1f}, Avg={avg_bpm:.1f}")
        
    logger.log("Session ended")
    player.close()
    if ser: ser.close()
    
    # Auto-retrain KNN model with new session data
    retrain_knn_model()
    
    print("EXIT_CLEAN")
    return player, logger, bpm_estimation

if __name__ == "__main__":
    main(parse_args())