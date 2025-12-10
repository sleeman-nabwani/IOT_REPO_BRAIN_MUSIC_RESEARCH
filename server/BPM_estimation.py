import time
from midi_player import MidiBeatSync
from logger import Logger

class BPM_estimation:
    def __init__(self, player: MidiBeatSync, logger: Logger) -> None:
        self.last_msg_time = time.time()
        self.player = player
        self.logger = logger
        self.last_recorded_bpm = 0
        
    def update_recorded_values(self,last_msg_time: float, last_recorded_bpm: float):
        self.last_msg_time = last_msg_time
        self.last_recorded_bpm = last_recorded_bpm

    def update_bpm(self, manual_mode=False):
        if manual_mode:
            return
            
        interval = time.time() - self.last_msg_time
        current_bpm = 60/interval
        if self.player.walkingBPM > current_bpm:
            self.player.set_BPM(current_bpm)
            self.logger.log(f"BPM updated from {self.player.walkingBPM} to {current_bpm}")
            self.logger.log_csv(time.time(), self.player.walkingBPM, self.last_recorded_bpm)