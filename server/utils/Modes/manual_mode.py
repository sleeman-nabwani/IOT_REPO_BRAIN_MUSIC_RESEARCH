from utils.Modes.base_mode import BaseMode

class ManualMode(BaseMode):
    def __init__(self, context):
        super().__init__(context)
        self.target_bpm = 100.0

    def set_bpm(self, bpm):
        self.target_bpm = max(40, min(240, float(bpm)))
        self.logger.log(f"MANUAL: Target set to {self.target_bpm:.1f}")

    def adjust_bpm(self, delta):
        new_bpm = self.target_bpm + delta
        self.set_bpm(new_bpm)
        return self.target_bpm

    def handle_step(self, now_ts, current_bpm):
        # In manual mode, we just enforce the target
        return self.target_bpm
