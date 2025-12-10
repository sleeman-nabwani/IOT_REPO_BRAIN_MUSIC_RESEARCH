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
            self.player.set_BPM(current_bpm)
            self.logger.log(f"BPM updated from {self.player.walkingBPM} to {current_bpm}")
            self.logger.log_csv(time.time(), self.player.walkingBPM, self.last_recorded_bpm)