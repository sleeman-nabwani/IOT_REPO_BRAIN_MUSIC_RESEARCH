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
    
    @patch('BPM_estimation.BPM_estimation.check_manual_bpm_update')
    @patch('serial.Serial')
    def test_manual_mode_120bpm(self, mock_serial_cls, mock_check_bpm):
        print("\n--- Starting Simulation Test: MANUAL Song -> 200 BPM ---")
        
        # 1. Setup Mock Serial Instance
        mock_serial = MagicMock()
        mock_serial_cls.return_value = mock_serial
        mock_serial.port = "MOCK_PORT"
        mock_serial.baudrate = 115200

        # Logic for check_manual_bpm_update:
        # Return 200.0 ONCE after 10 seconds.
        bpm_update_sent = False
        start_time_ref = time.time()
        
        def bpm_check_side_effect(*args, **kwargs):
            nonlocal bpm_update_sent
            elapsed = time.time() - start_time_ref
            if elapsed > 10.0 and not bpm_update_sent:
                bpm_update_sent = True
                print(f"[SIM] >>>> SIMULATING GUI UPDATE: SET BPM TO 200 <<<<")
                return 200.0
            return None

        mock_check_bpm.side_effect = bpm_check_side_effect

        # 3. Configure Logic for Manual Mode
        args = argparse.Namespace()
        
        # Absolute path to MIDI
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        args.midi_path = os.path.join(base_dir, "midi_files", "Technion_March1.mid")
        
        # KEY SETTINGS:
        args.manual = True
        args.bpm = None  # <--- Start with Default Song BPM
        
        start_time = time.time()
        start_time_ref = start_time # Sync the side effect time
        
        # State for mock walker
        state = {
            "last_step_time": start_time,
            "step_count": 0
        }

        # 4. Define non-blocking readline behavior
        def serial_read_side_effect():
            current_time = time.time()
            elapsed = current_time - start_time
            
            if elapsed > 15.0:
                print("\n[SIM] Timeout reached (15s), stopping simulation.")
                raise KeyboardInterrupt
            
            # Simulate a walker
            walker_bpm = 100.0
            step_interval_sec = 60.0 / walker_bpm
            
            # Generate a step line if enough time passed
            if current_time - state["last_step_time"] >= step_interval_sec:
                state["last_step_time"] = current_time
                state["step_count"] += 1
                
                if state["step_count"] % 10 == 0:
                     print(f"[SIM] Time {elapsed:.1f}s | Walker: {walker_bpm} BPM")

                foot = 1 if state["step_count"] % 2 == 0 else 0
                line = f"{current_time},{foot},{int(step_interval_sec*1000)},{walker_bpm}"
                return line.encode("utf-8")
            
            return b""

        mock_serial.readline.side_effect = serial_read_side_effect

        # 5. Run Main
        try:
            main(args)
        except KeyboardInterrupt:
            print("\n--- Simulation Ended ---")

if __name__ == '__main__':
    unittest.main()
