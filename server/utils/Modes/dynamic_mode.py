import statistics
from utils.Modes.base_mode import BaseMode

class DynamicMode(BaseMode):
    def __init__(self, context):
        super().__init__(context)
        self.hybrid_mode = False # "Cruise Control"
        
        # State
        self.locked_bpm = None
        self.start_hold_time = None
        self.stability_buffer = []  # To detect stable walking for locking
        self.unlock_buffer = []     # To detect change for unlocking
        self.unlock_start_time = None

    def set_hybrid(self, enabled: bool):
        self.hybrid_mode = enabled
        if not enabled:
            self.locked_bpm = None
            self.stability_buffer.clear()
            self.unlock_buffer.clear()

    def handle_step(self, now_ts, current_bpm):
        """
        Returns the target BPM.
        If Hybrid and Locked, returns lock.
        Else returns current_bpm (smoothed by context).
        """
        if not self.hybrid_mode:
            return current_bpm
        
        # --- Hybrid / Cruise Control Logic ---
        
        # 1. If Locked
        if self.locked_bpm is not None:
            # Check for Unlock condition (significant deviation)
            diff = abs(current_bpm - self.locked_bpm)
            UNLOCK_THRESHOLD = 15.0 # BPM
            
            if diff > UNLOCK_THRESHOLD:
                if self.unlock_start_time is None:
                    self.unlock_start_time = now_ts
                
                # If deviation persists for 1.5s
                if (now_ts - self.unlock_start_time) > 1.5:
                    self.logger.log(f"HYBRID: Unlocking (Diff {diff:.1f})")
                    self.locked_bpm = None
                    self.unlock_start_time = None
                    return current_bpm # Return to dynamic
            else:
                 self.unlock_start_time = None
                 
            return self.locked_bpm

        # 2. If Not Locked (Dynamic)
        # Check for Stability to Lock
        self.stability_buffer.append(current_bpm)
        if len(self.stability_buffer) > 5: self.stability_buffer.pop(0)

        if len(self.stability_buffer) == 5:
            delta = max(self.stability_buffer) - min(self.stability_buffer)
            if delta < 3.0: # Stable within 3 BPM
                 self.locked_bpm = statistics.mean(self.stability_buffer)
                 self.logger.log(f"HYBRID: Locked at {self.locked_bpm:.1f} BPM")
                 return self.locked_bpm
        
        return current_bpm
