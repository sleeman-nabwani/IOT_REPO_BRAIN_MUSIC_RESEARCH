import time
from midi_player import MidiBeatSync
from logger import Logger

class BPM_estimation:
    def __init__(self, player: MidiBeatSync, logger: Logger, manual_mode: bool = False, manual_bpm: float = None) -> None:
        self.last_msg_time = time.time()
        self.player = player
        self.logger = logger
        self.last_recorded_bpm = 0
        self.manual_mode = manual_mode
        self._pending_manual_bpm = manual_bpm
        self.smoothing_alpha = 0.05 # Default smoothing

    # Added this in order to change the smoothing factor at runtime:
    def set_smoothing_alpha(self, alpha: float):
        """Update the exponential smoothing factor (0.001 - 1.0)."""
        self.smoothing_alpha = max(0.001, min(1.0, float(alpha)))

    def set_manual_bpm(self, bpm: float | None):
        """Queue a manual BPM update to be applied on the next iteration."""
        self._pending_manual_bpm = bpm

    def set_manual_mode(self, enabled: bool):
        """Switch between manual and dynamic modes at runtime."""
        self.manual_mode = bool(enabled)

    def check_manual_bpm_update(self):
        # Return pending BPM if set, and clear it
        if self._pending_manual_bpm is not None:
            bpm = self._pending_manual_bpm
            self._pending_manual_bpm = None
            return bpm
        return None

    def update_recorded_values(self,last_msg_time: float, last_recorded_bpm: float):
        self.last_msg_time = last_msg_time
        self.last_recorded_bpm = last_recorded_bpm

    def update_bpm(self):
       # if in manual mode there is no need to update the bpm
        if self.manual_mode:
            return 
    
        # if no step-based BPM has been recorded yet, skip slowdown
        if self.last_recorded_bpm <= 0:
            return
        
        interval = time.time() - self.last_msg_time
        if interval <= 0:
            return
        current_bpm = 60 / interval
        if self.player.walkingBPM > current_bpm:
            # SMOOTHING ALGORITHM (Exponential Moving Average)
            alpha = self.smoothing_alpha
            
            # Calculate weighted average
            new_bpm = (self.player.walkingBPM * (1 - alpha)) + (current_bpm * alpha)
            
            self.player.set_BPM(new_bpm)
            self.logger.log(f"BPM decaying: {self.player.walkingBPM:.2f} -> {new_bpm:.2f}")
            self.logger.log_csv(time.time(), self.player.walkingBPM, self.last_recorded_bpm)
