import time
import serial
from logger import Logger

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