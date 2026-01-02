import time
import threading
from .midi_player import MidiBeatSync
from .logger import Logger
from .LGBM_predictor import LGBMPredictor
from collections import deque
from statistics import mean, stdev
import random

class BPM_estimation:
    def __init__(self, player: MidiBeatSync, logger: Logger, manual_mode: bool = False,
                manual_bpm: float = None, prediction_model: LGBMPredictor = None,
                smoothing_window: int = 3, stride: int = 1,
                run_type: str | None = None, hybrid_mode: bool = False) -> None:
        self.last_msg_time = time.time()
        self.player = player
        self.logger = logger
        self.last_recorded_bpm = 0
        self.manual_mode = manual_mode
        self._pending_manual_bpm = manual_bpm
        self.smoothing_alpha_up = 0.025   # Attack
        self.smoothing_alpha_down = 0.025 # Decay
        self.step_count = 0 
        self.prediction_model = prediction_model
        self._warmup_done = threading.Event()
        self._warmup_failed = False
        self._warmup_thread = None
        self.smoothing_window = smoothing_window
        self.stride = stride
        self.run_type = run_type or "dynamic"
        
        # Hybrid Mode
        self.hybrid_mode = hybrid_mode
        self.stability_buffer = deque(maxlen=10) 
        self.unlock_buffer = deque(maxlen=3)    
        self.locked_bpm = 0.0
        self.unlock_start_time = None
        self.UNLOCK_DURATION = 1.0 

        # Random Mode
        self.random_mode = False
        self.random_min = 100
        self.random_max = 140
        self.next_random_time = 0

        # State
        self.target_bpm = player.walkingBPM
        self.last_update_time = time.time()
        self.last_gui_log_time = time.time()

        if self.prediction_model:
            self._warmup_thread = threading.Thread(
                target=self._run_warmup, args=(player.walkingBPM,), daemon=True
            )
            self._warmup_thread.start()

    # ----------- Helper Methods -----------    

    def _run_warmup(self, initial_bpm: float | None):
        try:
            self.prediction_model.warmup(initial_bpm)
        except Exception:
            self._warmup_failed = True
        finally:
            self._warmup_done.set()

    def _process_hybrid_mode(self, new_bpm):
        """Matches walking pace (Dynamic) or locks to steady tempo (Manual)."""
        if not self.manual_mode:
            # DYNAMIC -> LOCK CHECK
            self.stability_buffer.append(new_bpm)
            if len(self.stability_buffer) == self.stability_buffer.maxlen:
                try:
                    dev = stdev(self.stability_buffer)
                except: 
                    dev = 0.0
                
                if dev < 5.0:
                    avg_bpm = mean(self.stability_buffer)
                    self.locked_bpm = avg_bpm
                    self.set_manual_mode(True)
                    self.set_manual_bpm(self.locked_bpm)
                    self.logger.log(f"cruise_control: Locked at {avg_bpm:.1f} BPM (StdDev: {dev:.2f})")
                    
        elif self.manual_mode:
            # LOCKED -> UNLOCK CHECK
            self.unlock_buffer.append(new_bpm)
            if len(self.unlock_buffer) == self.unlock_buffer.maxlen:
                current_avg = mean(self.unlock_buffer)
                
                if abs(current_avg - self.locked_bpm) > 8.0:
                        self.set_manual_mode(False)
                        self.logger.log(f"cruise_control: Disengaged (Avg: {current_avg:.1f} vs Locked: {self.locked_bpm:.1f})")
                        self.unlock_start_time = None
                else:
                    self.unlock_start_time = None

    def _update_random_drift(self, now_ts):
        if now_ts > self.next_random_time:
            self.target_bpm = random.uniform(self.random_min, self.random_max)
            self.next_random_time = now_ts + random.uniform(3.0, 8.0)
            self.logger.log(f"RANDOM: New Target {self.target_bpm:.1f}")

    def _apply_decay_logic(self, now_ts):
        """Slows down music if user stops walking."""
        interval = now_ts - self.last_msg_time
        if interval > 0:
            decay_limit = 60 / interval
            if decay_limit < self.target_bpm and self.step_count > 0:
                self.target_bpm = decay_limit

    def _perform_smoothing(self, current_bpm, dt):
        """Interpolates current BPM towards target."""
        diff = abs(self.target_bpm - current_bpm)
        
        if diff > 0.1:
            if self.target_bpm > current_bpm:
                alpha = self.smoothing_alpha_up
                # Adaptive Boost for catching up to sprints
                bpm_diff = self.target_bpm - current_bpm
                if bpm_diff > 5.0:
                    boost_factor = 1.0 + (bpm_diff - 5.0) * 0.1
                    alpha *= min(boost_factor, 4.0) 
            else:
                alpha = self.smoothing_alpha_down

            step = (self.target_bpm - current_bpm) * (alpha * 25.0) * dt
            
            # Gradual startup ramp (first 5 steps)
            if self.step_count < 5:
                max_step = 10.0 * dt
                if abs(step) > max_step:
                    step = max_step if step > 0 else -max_step
            
            # Clamp step
            if abs(step) > diff:
                new_bpm = self.target_bpm
            else:
                new_bpm = current_bpm + step
            
            self.player.set_BPM(new_bpm)
            
            if abs(new_bpm - current_bpm) > 1.0:
                self.logger.log(f"BPM sliding: {current_bpm:.2f} -> {new_bpm:.2f} (Target: {self.target_bpm:.2f})")

    # ----------- Setters -----------
    def set_smoothing_alpha_up(self, alpha: float):
        self.smoothing_alpha_up = max(0.001, min(1.0, float(alpha)))

    def set_smoothing_alpha_down(self, alpha: float):
        self.smoothing_alpha_down = max(0.001, min(1.0, float(alpha)))

    def set_manual_bpm(self, bpm: float | None):
        self._pending_manual_bpm = bpm

    def set_manual_mode(self, enabled: bool):
        self.manual_mode = bool(enabled)
        if enabled:
           self.stability_buffer.clear()
        else:
           self.unlock_buffer.clear()
           self.unlock_start_time = None

    def set_random_mode(self, enabled: bool, min_bpm: int = 100, max_bpm: int = 140):
        self.random_mode = enabled
        self.random_min = min_bpm
        self.random_max = max_bpm
        if enabled:
            self.logger.log(f"Random Mode ENABLED ({min_bpm}-{max_bpm} BPM)")
        else:
            self.logger.log("Random Mode DISABLED")

    def check_manual_bpm_update(self):
        if self._pending_manual_bpm is not None:
            bpm = self._pending_manual_bpm
            self._pending_manual_bpm = None
            return bpm
        return None

    def update_recorded_values(self,last_msg_time: float, last_recorded_bpm: float):
        self.last_msg_time = last_msg_time
        self.last_recorded_bpm = last_recorded_bpm

    # ----------- Main Loop -----------

    def register_button_delta(self, delta: float):
        if self.manual_mode:
            current_bpm = self.player.walkingBPM
            new_bpm = max(40, min(240, current_bpm + delta))
            
            self.player.set_BPM(new_bpm)
            self.target_bpm = new_bpm
            self.locked_bpm = new_bpm
            
            self.logger.log(f"MANUAL: Adjusted BPM to {new_bpm:.1f} (Delta {delta})")
            return new_bpm
        return None

    def register_step(self, new_bpm, instant_bpm=None):
        if self.hybrid_mode:
            self._process_hybrid_mode(new_bpm)

        self.target_bpm = new_bpm
        self.last_recorded_bpm = new_bpm
        self.last_msg_time = time.time()
        self.step_count += 1
        
        if self.prediction_model and self._warmup_done.is_set() and not self._warmup_failed:
            try:
                self.prediction_model.add_step(new_bpm, instant_bpm)
                pred = self.prediction_model.predict_next(
                    smoothing_window=self.smoothing_window,
                    stride=self.stride,
                    run_type=self.run_type,
                )
                if pred is not None:
                    self.target_bpm = float(pred) * 0.65 + new_bpm * 0.35
            except Exception:
                pass

    def _run_warmup(self, initial_bpm: float | None):
        try:
            self.prediction_model.warmup(initial_bpm, run_type=self.run_type)
        except Exception:
            self._warmup_failed = True
        finally:
            self._warmup_done.set()


    def update_recorded_values(self,last_msg_time: float, last_recorded_bpm: float):
        # Keeps legacy compatibility, but register_step is preferred.
        self.last_msg_time = last_msg_time
        self.last_recorded_bpm = last_recorded_bpm

    def update_bpm(self):
        now_ts = time.time()
        dt = now_ts - self.last_update_time
        self.last_update_time = now_ts

        if self.manual_mode:
            if now_ts - self.last_gui_log_time > 0.1:
                try:
                    song_bpm = self.player.walkingBPM
                    self.logger.log_data(now_ts, song_bpm, self.target_bpm or song_bpm, step_event=False)
                except Exception:
                    pass
                self.last_gui_log_time = now_ts
            return
        
        if self.random_mode:
            self._update_random_drift(now_ts)
        else:
            # 3. Decay Logic (If user stops walking)
            interval = now_ts - self.last_msg_time
            if interval > 0:
                decay_limit = 60 / interval
                if decay_limit < self.target_bpm:
                    # Only decay if valid steps have started
                    if self.step_count > 0:
                        self.target_bpm = decay_limit

        self._perform_smoothing(self.player.walkingBPM, dt)
        
        # Always log data for the graph (Heartbeat ~10Hz)
        if now_ts - self.last_gui_log_time > 0.1:
            try:
                song_bpm = self.player.walkingBPM
                # In dynamic mode, target_bpm is the "Goal". Walking BPM is current song speed.
                self.logger.log_data(now_ts, song_bpm, self.target_bpm, step_event=False)
            except Exception:
                pass
            self.last_gui_log_time = now_ts
