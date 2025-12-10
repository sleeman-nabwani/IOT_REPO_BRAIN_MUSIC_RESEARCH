import sys
import os
import time
import argparse
import unittest
from unittest.mock import MagicMock, patch

# Add server directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

# Import main from server
from main import main

class TestManualMode(unittest.TestCase):
    
    @patch('serial.Serial')
    def test_manual_mode_120bpm(self, mock_serial_cls):
        print("\n--- Starting Simulation Test: MANUAL 120 BPM ---")
        
        # 1. Setup Mock Serial Instance
        mock_serial = MagicMock()
        mock_serial_cls.return_value = mock_serial
        mock_serial.port = "MOCK_PORT"
        mock_serial.baudrate = 115200

        # 2. Configure Logic for Manual 120 BPM
        args = argparse.Namespace()
        
        # Absolute path to MIDI
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        args.midi_path = os.path.join(base_dir, "midi_files", "Technion_March1.mid")
        
        # KEY SETTINGS:
        args.manual = True
        args.bpm = None  # <--- Use Default Song BPM
        
        start_time = time.time()
        
        # State for mock walker
        state = {
            "last_step_time": start_time,
            "step_count": 0
        }

        # 3. Define non-blocking readline behavior
        # Use a flag to ensure command is sent only once
        cmd_sent = False
        
        def side_effect():
            nonlocal cmd_sent
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Scenario:
            # 0-10s: Normal Manual Mode (Song BPM)
            # 10s:   User sends command to CHANGE Manual BPM to 200
            
            if elapsed >= 10 and not cmd_sent:
                cmd_sent = True
                print(f"[SIM] >>>> SENDING COMMAND: CHANGE MANAUL BPM TO 200 <<<<")
                return b"CMD:BPM:200\n"

            # Simulate a walker (BPM doesn't matter for the music, but logs need valid lines)
            walker_bpm = 100.0
            step_interval_sec = 60.0 / walker_bpm
            
            # Generate a step line if enough time passed
            if current_time - state["last_step_time"] >= step_interval_sec:
                state["last_step_time"] = current_time
                state["step_count"] += 1
                
                if state["step_count"] % 10 == 0:
                     print(f"[SIM] Time {elapsed:.1f}s | Walker: {walker_bpm} BPM | Mode: MANUAL (Music should be constant)")

                foot = 1 if state["step_count"] % 2 == 0 else 0
                line = f"{current_time},{foot},{int(step_interval_sec*1000)},{walker_bpm}"
                return line.encode("utf-8")
            
            # Non-blocking return
            return b""

        mock_serial.readline.side_effect = side_effect

        # 4. Run Main
        try:
            main(args)
        except KeyboardInterrupt:
            print("\n--- Simulation Ended ---")

if __name__ == '__main__':
    unittest.main()
