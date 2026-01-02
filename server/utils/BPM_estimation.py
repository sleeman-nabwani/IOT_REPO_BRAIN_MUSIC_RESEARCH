import time
import threading
from .midi_player import MidiBeatSync
from .logger import Logger
from .LGBM_predictor import LGBMPredictor

# Import Modes
from .Modes.manual_mode import ManualMode
from .Modes.random_mode import RandomMode
from .Modes.dynamic_mode import DynamicMode

class BPM_estimation:
    def __init__(self, player: MidiBeatSync, logger: Logger, manual_mode: bool = False,
                manual_bpm: float = None, prediction_model: LGBMPredictor = None,
                smoothing_window: int = 3, stride: int = 1,
                run_type: str | None = None, hybrid_mode: bool = False) -> None:
        
        self.player = player
        self.logger = logger
        self.prediction_model = prediction_model
        
        # Shared Context State
        self.step_count = 0
        self.last_msg_time = time.time()
        self.last_update_time = time.time()
        self.last_gui_log_time = time.time()
        
        # Modes
        self.manual_mode_obj = ManualMode(self)
        self.random_mode_obj = RandomMode(self)
        self.dynamic_mode_obj = DynamicMode(self)
        
        # Active State
        self.active_mode = "dynamic" # dynamic, random, manual
        
        # Configuration
        if manual_mode:
            self.set_manual_mode(True)
            if manual_bpm: self.set_manual_bpm(manual_bpm)
        
        self.dynamic_mode_obj.set_hybrid(hybrid_mode)

        # Smoothing Params (Context level for final output)
        self.smoothing_alpha_up = 0.025
        self.smoothing_alpha_down = 0.025
        self.target_bpm = player.walkingBPM

        # ML Warmup
        self._warmup_done = threading.Event()
        self._warmup_failed = False
        if self.prediction_model:
            threading.Thread(target=self._run_warmup, args=(player.walkingBPM,), daemon=True).start()

    # ----------- State Switches -----------
    def set_manual_mode(self, enabled: bool):
        if enabled:
            self.active_mode = "manual"
            self.manual_mode_obj.activate()
        else:
            if self.active_mode == "manual":
                self.active_mode = "dynamic" # Fallback to dynamic
                self.dynamic_mode_obj.activate()

    def set_manual_bpm(self, bpm: float):
        self.manual_mode_obj.set_bpm(bpm)

    def set_random_mode(self, enabled: bool, span: float = 0.20):
        if enabled:
            self.active_mode = "random"
            self.random_mode_obj.set_span(span)
            self.random_mode_obj.activate()
        else:
            if self.active_mode == "random":
                self.active_mode = "dynamic"
                self.dynamic_mode_obj.activate()

    def set_random_span(self, span: float):
        self.random_mode_obj.set_span(span)

    def set_random_gamified(self, enabled: bool):
        self.random_mode_obj.set_gamified(enabled)

    # ----------- Input Handling -----------
    def register_step(self, new_bpm, instant_bpm=None):
        """Called when a new step is detected."""
        self.last_msg_time = time.time()
        self.step_count += 1
        
        # ML Prediction Hook
        if self.prediction_model and self._warmup_done.is_set() and not self._warmup_failed:
            try:
                self.prediction_model.add_step(new_bpm, instant_bpm)
                pred = self.prediction_model.predict_next()
                if pred: 
                    # Blending prediction
                     new_bpm = float(pred) * 0.65 + new_bpm * 0.35
            except: pass

        # Notify active mode of Step Event
        if self.active_mode == "random":
             self.random_mode_obj.on_step(new_bpm)

        # Dynamic Mode Buffers update
        self.dynamic_mode_obj.stability_buffer.append(new_bpm)
        self.target_bpm = new_bpm # Default target if dynamic

    def register_button_delta(self, delta: float):
        """Hardware button press."""
        # Force manual mode if button pressed?
        # Current logic: If in manual mode, adjust it.
        if self.active_mode == "manual":
            new_val = self.manual_mode_obj.adjust_bpm(delta)
            self.player.set_BPM(new_val)
            self.target_bpm = new_val
            
            # Notify GUI
            import sys
            print(f"GUI_SYNC:MANUAL_BPM:{new_val}")
            sys.stdout.flush()
            return new_val
        return None

    # ----------- Main Loop -----------
    def update_bpm(self):
        """Called ~10Hz by main loop."""
        now_ts = time.time()
        dt = now_ts - self.last_update_time
        self.last_update_time = now_ts
        
        current_bpm = self.player.walkingBPM
        
        # 1. Determine Target from Active Mode
        if self.active_mode == "manual":
            outcome_target = self.manual_mode_obj.handle_step(now_ts, current_bpm)
        elif self.active_mode == "random":
            outcome_target = self.random_mode_obj.handle_step(now_ts, current_bpm)
        else:            
            candidate = self.dynamic_mode_obj.handle_step(now_ts, current_bpm)
            
            # Decay Check
            interval = now_ts - self.last_msg_time
            if interval > 0:
                decay_limit = 60.0 / interval
                if decay_limit < candidate and self.step_count > 0:
                     candidate = decay_limit
            
            outcome_target = candidate

        # 2. Smooth towards Target
        self.target_bpm = outcome_target
        self._perform_smoothing(current_bpm, dt)
        
        # 3. Logging
        if now_ts - self.last_gui_log_time > 0.1:
            try:
                self.logger.log_data(now_ts, current_bpm, self.target_bpm, step_event=False)
            except: pass
            self.last_gui_log_time = now_ts

    def _perform_smoothing(self, current_bpm, dt):
        """Interpolates current BPM towards target."""
        diff = abs(self.target_bpm - current_bpm)
        if diff > 0.1:
            if self.target_bpm > current_bpm:
                alpha = self.smoothing_alpha_up
                # Boost logic
                bpm_diff = self.target_bpm - current_bpm
                if bpm_diff > 5.0:
                    boost = 1.0 + (bpm_diff - 5.0) * 0.1
                    alpha *= min(boost, 4.0)
            else:
                alpha = self.smoothing_alpha_down
            
            # Step calc
            step = (self.target_bpm - current_bpm) * (alpha * 25.0) * dt
            
            # Startup clamp
            if self.step_count < 5:
                max_step = 10.0 * dt
                if abs(step) > max_step: step = max_step if step > 0 else -max_step
            
            # Final apply
            if abs(step) > diff: new_bpm = self.target_bpm
            else: new_bpm = current_bpm + step
            
            self.player.set_BPM(new_bpm)

    def _run_warmup(self, initial_bpm):
        try: self.prediction_model.warmup(initial_bpm)
        except: self._warmup_failed = True
        finally: self._warmup_done.set()
    
    # Legacy Setters
    def set_smoothing_alpha_up(self, a): self.smoothing_alpha_up = float(a)
    def set_smoothing_alpha_down(self, a): self.smoothing_alpha_down = float(a)
