import subprocess
import sys
import threading
import json
from pathlib import Path
import os

class SubprocessManager:
    """
    Manages the 'main.py' engine process.
    - Launches it as a subprocess.
    - Writes commands to its STDIN.
    - Reads logs from its STDOUT.
    """
    def __init__(self, midi_path, serial_port, manual_mode, manual_bpm, smoothing_window, stride, log_callback, session_dir_callback, data_callback=None, session_name=None):
        self.log_callback = log_callback
        self.session_dir_callback = session_dir_callback
        self.data_callback = data_callback
        self.process = None
        self.running = False
        
        # Build Command Arguments
        # Use absolute path to ensure main.py is found regardless of CWD
        
        # Revert to sys.executable as it maps to the active VENV
        cmd = [sys.executable, "main.py", midi_path]
        if manual_mode:
            cmd.append("--manual")
            if manual_bpm:
                cmd.extend(["--bpm", str(manual_bpm)])
        
        if serial_port:
             cmd.extend(["--serial-port", str(serial_port)]) 
        
        # We pass initial config via flags
        cmd.extend(["--smoothing", str(smoothing_window)])
        cmd.extend(["--stride", str(stride)])
        
        if session_name:
             cmd.extend(["--session-name", str(session_name)])
        
        # Launch Process
        try:
            # We use bufsize=1 for line buffering
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # Capture separately
                text=True,
                bufsize=1,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Execute INSIDE server/ folder (parent of utils)
            )
            self.running = True
            
            # Start Background Reader Threads
            self.reader_thread = threading.Thread(target=self._read_stdout, daemon=True)
            self.reader_thread.start()
            
            self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
            self.stderr_thread.start()
            
        except Exception as e:
            self._log(f"Failed to start engine: {e}")

        # Debug logging of command (disabled for clean production)
        # self._log(f"Executing: {' '.join(cmd)}")

    def _log(self, msg):
        # print(f"[GUI_DEBUG] {msg}") # Debug print disabled
        if self.log_callback: self.log_callback(msg)

    def _read_stderr(self):
        """Reads lines from the subprocess STDERR and logs them as errors."""
        while self.running and self.process:
            try:
                line = self.process.stderr.readline()
                if not line: break
                line = line.strip()
                if line:
                    self._log(f"[Stderr] {line}")
            except Exception:
                break

    def _read_stdout(self):
        """Reads lines from the subprocess STDOUT and logs them."""
        while self.running and self.process:
            try:
                line = self.process.stdout.readline()
                if not line: break
                line = line.strip()
                
                # Check for special signals
                if line.startswith("SESSION_DIR:"):
                     path_str = line.split(":", 1)[1]
                     if self.session_dir_callback:
                         self.session_dir_callback(Path(path_str))
                     continue # Don't log this protocol line
                
                # Check for Data Packet (RAM Pipe)
                if line.startswith("DATA_PACKET:"):
                     if self.data_callback:
                         try:
                             json_str = line.split(":", 1)[1]
                             data = json.loads(json_str)
                             self.data_callback(data)
                         except: pass
                     continue

                if line == "EXIT_CLEAN":
                    self.running = False
                    break

                self._log(f"[Engine] {line}")
            except Exception:
                break
            
    def send_command(self, cmd_str):
        """Writes a line to the subprocess STDIN."""
        if self.process and self.running:
            try:
                self.process.stdin.write(cmd_str + "\n")
                self.process.stdin.flush()
            except Exception as e:
                self._log(f"Send Error: {e}")

    def update_manual_bpm(self, bpm):
        self.send_command(f"SET_MANUAL_BPM:{bpm}")

    def set_manual_mode(self, enabled):
        # Main doesn't support switching mode at runtime via STDIN yet, 
        # but we can implement it if needed. For now, just log.
        pass

    def update_smoothing_alpha_up(self, alpha):
        self.send_command(f"SET_ALPHA_UP:{alpha}")

    def update_smoothing_alpha_down(self, alpha):
        self.send_command(f"SET_ALPHA_DOWN:{alpha}")

    def update_esp_config(self, cmd_type, value):
        if cmd_type == "window":
            self.send_command(f"SET_WINDOW:{value}")
        elif cmd_type == "stride":
            self.send_command(f"SET_STRIDE:{value}")

    def stop(self):
        self.running = False
        if self.process:
            self.send_command("QUIT")
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
