import time
import threading
from .midi_player import MidiBeatSync
from .logger import Logger
from .LGBM_predictor import LGBMPredictor

class BPM_estimation:
    def __init__(self, player: MidiBeatSync, logger: Logger, manual_mode: bool = False,
                manual_bpm: float = None, prediction_model: LGBMPredictor = None,
                smoothing_window: int = 3, stride: int = 1) -> None:
        self.last_msg_time = time.time()
        self.player = player
        self.logger = logger
        self.last_recorded_bpm = 0
        self.manual_mode = manual_mode
        self._pending_manual_bpm = manual_bpm
        self.smoothing_alpha_up = 0.025   # Smoothing when speeding up (Attack)
        self.smoothing_alpha_down = 0.025 # Smoothing when slowing down (Decay)
        self.step_count = 0 # Track number of steps for delayed start
        self.prediction_model = prediction_model
        self._warmup_done = threading.Event()
        self._warmup_failed = False
        self._warmup_thread = None
        self.smoothing_window = smoothing_window
        self.stride = stride
        
        # TARGET BPM: This is where we WANT to be.
        # The 'walkingBPM' is where we ARE currently.
        # We will smoothly slide 'walkingBPM' -> 'target_bpm' every loop.
        self.target_bpm = player.walkingBPM
        
        # Time-Based Smoothing
        self.last_update_time = time.time()
        self.last_gui_log_time = time.time()

        # Warm-up the predictor off the main path to avoid first-step stall.
        if self.prediction_model:
            self._warmup_thread = threading.Thread(
                target=self._run_warmup, args=(player.walkingBPM,), daemon=True
            )
            self._warmup_thread.start()

    # Added this in order to change the smoothing factor at runtime:
    # Added this in order to change the smoothing factor at runtime:
    def set_smoothing_alpha_up(self, alpha: float):
        """Update the Attack smoothing factor (0.001 - 1.0)."""
        self.smoothing_alpha_up = max(0.001, min(1.0, float(alpha)))

    def set_smoothing_alpha_down(self, alpha: float):
        """Update the Decay smoothing factor (0.001 - 1.0)."""
        self.smoothing_alpha_down = max(0.001, min(1.0, float(alpha)))

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

    def register_step(self, new_bpm, instant_bpm=None):
        """
        Called when a NEW STEP is detected. 
        Instead of changing music instantly, we just update the TARGET.
        The update_bpm() loop will handle the smooth transition.
        """
        self.target_bpm = new_bpm
        self.last_recorded_bpm = new_bpm
        self.last_msg_time = time.time() # Reset the decay timer
        self.step_count += 1
        
        # Prediction model (LightGBM) — only after warmup completes.
        if self.prediction_model and self._warmup_done.is_set() and not self._warmup_failed:
            try:
                self.prediction_model.add_step(new_bpm, instant_bpm)
                pred = self.prediction_model.predict_next(
                    smoothing_window=self.smoothing_window,
                    stride=self.stride,
                )
                if pred is not None:
                    # Blend to avoid sudden jumps while still using fresh prediction.
                    self.target_bpm = float(pred) * 0.65 + new_bpm * 0.35
            except Exception:
                pass

    def _run_warmup(self, initial_bpm: float | None):
        try:
            self.prediction_model.warmup(initial_bpm)
        except Exception:
            self._warmup_failed = True
        finally:
            self._warmup_done.set()


    def update_recorded_values(self,last_msg_time: float, last_recorded_bpm: float):
        # Keeps legacy compatibility, but register_step is preferred.
        self.last_msg_time = last_msg_time
        self.last_recorded_bpm = last_recorded_bpm

    def update_bpm(self):
        """
        Main Loop Function.
        This runs ~100 times per second.
        It moves the current BPM a tiny bit closer to the Target BPM every time.
        """
        now_ts = time.time()

        # Manual mode: still emit data every loop so the graph updates even without steps.
        if self.manual_mode:
            if now_ts - self.last_gui_log_time > 0.1:
                try:
                    song_bpm = self.player.walkingBPM
                    self.logger.log_data(now_ts, song_bpm, self.target_bpm or song_bpm, step_event=False)
                except Exception:
                    pass
                self.last_gui_log_time = now_ts
            return
        
        # 3. Decay Logic (If user stops walking)
        interval = now_ts - self.last_msg_time
        if interval > 0:
            decay_limit = 60 / interval
            if decay_limit < self.target_bpm:
                # Only decay if valid steps have started
                if self.step_count > 0:
                    self.target_bpm = decay_limit

        # 4. Smoothing Logic (Target Seeking)
        # We slide the current music BPM towards the Target BPM.
        current_bpm = self.player.walkingBPM
        
        # Calculate Delta Time (dt)
        dt = now_ts - self.last_update_time
        self.last_update_time = now_ts
        
        # optimized strictness: only update if diff is > 0.1
        diff = abs(self.target_bpm - current_bpm)
        
        if diff > 0.1:
            # Scale alpha by dt to make it frame-rate independent.
            # Base rate assumption: 50Hz (0.02s per frame).
            # Select Directional Smoothing Factor
            if self.target_bpm > current_bpm:
                # Acceleration (Attack)
                alpha = self.smoothing_alpha_up
                
                # --- ADAPTIVE BOOST ---
                # If the target is FAR ahead (e.g. user started sprinting),
                # we boost the alpha to catch up faster.
                bpm_diff = self.target_bpm - current_bpm
                if bpm_diff > 5.0:
                    # Boost Factor: Increases linearly with distance
                    # e.g., diff=15 -> boost=1+(15-5)*0.1 = 2.0x faster
                    boost_factor = 1.0 + (bpm_diff - 5.0) * 0.1
                    # Cap the boost to prevent snapping
                    boost_factor = min(boost_factor, 4.0) 
                    alpha *= boost_factor
            else:
                # Deceleration (Decay)
                alpha = self.smoothing_alpha_down

            speed_factor = alpha * 25.0 
            
            # Simple Linear Interpolation
            step = (self.target_bpm - current_bpm) * speed_factor * dt
            
            # GRADUAL STARTUP: If we are just starting (first 5 steps), limit the change speed.
            # Max change = 10 BPM per second
            if self.step_count < 5:
                max_change_per_sec = 10.0
                max_step = max_change_per_sec * dt
                if abs(step) > max_step:
                    step = max_step if step > 0 else -max_step
            
            # Clamp step to not exceed the difference (arrive at target)
            if abs(step) > diff:
                new_bpm = self.target_bpm
            else:
                new_bpm = current_bpm + step
            
            self.player.set_BPM(new_bpm)
            
            # Log significant changes (Reduced spam)
            if abs(new_bpm - current_bpm) > 1.0:
                self.logger.log(f"BPM sliding: {current_bpm:.2f} -> {new_bpm:.2f} (Target: {self.target_bpm:.2f})")
            
        # Always emit a packet periodically so the GUI updates even without diff
        if now_ts - self.last_gui_log_time > 0.1:
            try:
                song_bpm = self.player.walkingBPM
                self.logger.log_data(now_ts, song_bpm, self.target_bpm, step_event=False)
            except Exception:
                pass
            self.last_gui_log_time = now_ts

