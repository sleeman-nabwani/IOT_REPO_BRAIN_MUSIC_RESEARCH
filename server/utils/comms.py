import time
import serial
import sys
import threading
from .logger import Logger
from .safety import safe_execute

def start_stdin_listener(command_queue):
    """
    Starts a background thread that listens to sys.stdin and pushes lines to command_queue.
    """
    def _listener():
        while True:
            try:
                line = sys.stdin.readline()
                if not line: break
                line = line.strip()
                if line: command_queue.put(line)
            except: break
    
    t = threading.Thread(target=_listener, daemon=True)
    t.start()
    return t

@safe_execute
def send_config_command(ser: serial.Serial, logger: Logger, cmd_prefix: str,
                        value: int, desc: str, expected_ack_prefix: str,
                        retries: int = 3):
    """Helper to send configuration for the parameters in the ESP32."""
    #creating the command string
    cmd = f"{cmd_prefix},{value}\n"
    #encoding the command string
    encoded_cmd = cmd.encode("utf-8")
    #sending the command to the ESP32
    for _ in range(retries):
        logger.log(f"Setting {desc} to {value}")
        ser.write(encoded_cmd)
        time.sleep(0.1)
        resp = ser.readline()
        resp_str = resp.decode('utf-8', errors='ignore').strip() if resp else ""
        
        # We check if the response starts with the specific expected ACK prefix
        if resp_str.startswith(expected_ack_prefix):
            logger.log(f"{desc.capitalize()} set response: {resp_str}")
            return True
        
        logger.log(f"Unexpected or no ACK for {desc} (got: {resp_str!r}, expected: {expected_ack_prefix}, retrying...")
        
    logger.log(f"Failed to set {desc} after {retries} attempts")
    return False

@safe_execute
def send_handshake_command(ser: serial.Serial, logger: Logger, command: bytes, expected_ack: str, retries: int = 5) -> bool:
    """Helper to send handshake commands and wait for ACK."""
    for _ in range(retries):
        ser.write(command)
        time.sleep(0.1)
        resp = ser.readline()
        resp_str = resp.decode("utf-8", errors="ignore").strip() if resp else ""
        if resp_str == expected_ack:
            logger.log(f"{expected_ack} received")
            return True
        logger.log(f"Unexpected or no ACK (got: {resp_str!r}), retrying...")
    return False

@safe_execute
def session_handshake(ser: serial.Serial, logger: Logger, smoothing_window: int = 3, stride: int = 2) -> bool:
    """Perform RESET/START handshake with bounded retries."""
    # allow the ESP to finish boot messages, then clear the buffer
    time.sleep(0.5)
    ser.reset_input_buffer()

    # Optional: Set smoothing window before starting
    if smoothing_window != 3:
        if not send_config_command(ser, logger, "SET_WINDOW", smoothing_window, "smoothing window", "ACK,WINDOW"):
             logger.log("Warning: Failed to set smoothing window")

    # Optional: Set update stride before starting
    if stride != 2:
        if not send_config_command(ser, logger, "SET_STRIDE", stride, "update stride", "ACK,STRIDE"):
             logger.log("Warning: Failed to set update stride")

    if not send_handshake_command(ser, logger, b"RESET\n", "ACK,RESET"):
        logger.log("RESET handshake failed")
        return False

    if not send_handshake_command(ser, logger, b"START\n", "ACK,START"):
        logger.log("START handshake failed")
        return False

    logger.log("Session handshake completed")
    return True

@safe_execute
def process_input_commands(command_queue, ser, logger, bpm_estimation, player, stop_event):
    """
    Drains the input command queue from the GUI.
    Handles configuration changes (Window, Alpha, Manual BPM) and Quit signal.
    """
    while not command_queue.empty():
        cmd = command_queue.get_nowait()
        
        # String Command (STDIN/Subprocess)
        if isinstance(cmd, str):
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
                stop_event.set()
                return # Stop processing


@safe_execute
def read_all_sensor_steps(ser, logger):
    """
    DRAINS the serial buffer.
    Reads ALL available lines and returns the very last valid step.
    This prevents 'Buffer Lag' / 'Spikes' caused by accumulating data during sleep.
    
    ESP32 sends: timestamp, foot, instantBPM, averageBPM
    Returns: (ts, foot, instant_bpm, avg_bpm) or None if no valid data.
    """
    latest_valid_step = None
    lines_read = 0
    
    while ser.in_waiting > 0:
        raw_line = ser.readline()
        lines_read += 1
        
        try:
            step = raw_line.decode("utf-8", errors="ignore").strip()
            # logger.log(f"Step received: {step}") # Verbose, maybe comment out for production
            
            parts = step.split(",")
            if len(parts) != 4: continue
            
            ts_str, foot_str, instant_bpm_str, avg_bpm_str = parts
            
            ts = int(ts_str)
            foot = int(foot_str)
            instant_bpm = float(instant_bpm_str)
            avg_bpm = float(avg_bpm_str)
            
            # FILTER: Ignore unrealistic BPM values (too high = noise)
            if instant_bpm > 300:
                logger.log(f"Ignoring unrealistic BPM: {instant_bpm}")
                continue
                
            latest_valid_step = (ts, foot, instant_bpm, avg_bpm)
            
        except ValueError:
            continue
            
    if lines_read > 1:
        # Debug log to confirm limiting is working
        # logger.log(f"Packet Drain: Processed {lines_read} lines at once.")
        pass
        
    return latest_valid_step