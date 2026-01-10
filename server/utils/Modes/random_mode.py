import random
from utils.Modes.base_mode import BaseMode

class RandomMode(BaseMode):
    def __init__(self, context, span: float = 0.20, gamified: bool = False, 
                 simple_threshold: float = 5.0, simple_steps: int = 20, simple_timeout: float = 30.0):
        super().__init__(context)
        # Game State
        self.game_target = None
        self.target_assigned_time = None
        self.match_start_time = None
        
        # Simple Mode State
        self.matched_step_counter = 0

        # Configuration (from init params, which come from GUI)
        self.span = span
        self.gamified = gamified
        self.simple_threshold = simple_threshold
        self.simple_steps = simple_steps
        self.simple_timeout = simple_timeout

    def set_simple_threshold(self, threshold):
        self.simple_threshold = float(threshold)
        self.logger.log(f"RANDOM: Simple threshold set to {self.simple_threshold} BPM")

    def set_simple_steps(self, steps):
        self.simple_steps = int(steps)
        self.logger.log(f"RANDOM: Simple steps set to {self.simple_steps}")

    def set_simple_timeout(self, seconds):
        self.simple_timeout = float(seconds)
        self.logger.log(f"RANDOM: Simple timeout set to {self.simple_timeout}s")

    def set_span(self, span):
        self.span = span
        self.logger.log(f"GAME: Difficulty updated to ±{int(span*100)}%")

    def set_gamified(self, enabled):
        self.gamified = enabled
        mode_str = "GAMIFIED" if enabled else "SIMPLE (Step-based)"
        self.logger.log(f"RANDOM: Mode switched to {mode_str}")
        # Reset current round
        self.game_target = None

    def activate(self):
        super().activate()
        # Reset game state on entry
        self.game_target = None
        self.match_start_time = None
        self.target_assigned_time = None
        self.matched_step_counter = 0

    def on_step(self, bpm, now_ts):
        """Called on every step."""
        if self.gamified or self.game_target is None:
             return
        
        diff = abs(bpm - self.game_target)
        if diff < self.simple_threshold:
            self.matched_step_counter += 1
            if self.matched_step_counter % 5 == 0: 
                 self.logger.log(f"SIMPLE: Matched {self.matched_step_counter}/{self.simple_steps} steps...")
                 
            if self.matched_step_counter >= self.simple_steps:
                 self.logger.log(f"SIMPLE: Completed {self.simple_steps} steps! Next target.")
                 # Use passed timestamp
                 self._pick_new_target(now_ts)
                 self.matched_step_counter = 0
        else:
            if self.matched_step_counter > 0:
                 self.logger.log("SIMPLE: Lost match. Resetting counter.")
            self.matched_step_counter = 0

    def handle_step(self, now_ts, current_bpm, dt):
        """
        Orchestrates Random Mode (Gamified or Simple).
        Returns (target, smoothed_next).
        """
        # 1. Initialization
        if self.game_target is None:
            self._pick_new_target(now_ts)
            return self.game_target, self._smooth_towards(current_bpm, self.game_target, dt)
            
        # --- SIMPLE MODE ---
        if not self.gamified:
             # Timeout Check (Fallback if user can't match pace)
             if self.target_assigned_time and (now_ts - self.target_assigned_time > self.simple_timeout):
                 self.logger.log(f"SIMPLE: Timeout ({self.simple_timeout}s)! Next target.")
                 self._pick_new_target(now_ts)
                 self.matched_step_counter = 0
             
             # Logic is also handled in on_step()
             return self.game_target, self._smooth_towards(current_bpm, self.game_target, dt)

        # --- GAMIFIED MODE ---
        # 2. Timeout Check
        if self.target_assigned_time and (now_ts - self.target_assigned_time > self.simple_timeout):
             self.logger.log(f"GAME: Timeout ({self.simple_timeout}s)! Skipping...")
             self._pick_new_target(now_ts)
             return self.game_target, self._smooth_towards(current_bpm, self.game_target, dt)

        # 3. Match & Hold Check
        diff = abs(current_bpm - self.game_target)

        # Matched?
        if diff < self.simple_threshold:
            if self.match_start_time is None:
                self.match_start_time = now_ts
                self.logger.log("GAME: Matched! Hold it...")
            
            # Held long enough?
            held_duration = now_ts - self.match_start_time
            if held_duration > self.simple_steps:
                self.logger.log(f"GAME: Success! Held for {self.simple_steps}s.")
                self._pick_new_target(now_ts)
        else:
            # Lost the match
            if self.match_start_time is not None:
                self.logger.log("GAME: Lost match! Try again.")
                self.match_start_time = None
        
        return self.game_target, self._smooth_towards(current_bpm, self.game_target, dt)

    def _pick_new_target(self, now_ts):
        """Generates a new random target BPM."""
        base = self.context.player.songBPM
        span = base * self.span
        
        attempts = 0
        new_target = self.game_target
        
        while True:
            new_target = random.uniform(max(40, base-span), min(200, base+span))
            if self.game_target is None: break
            if abs(new_target - self.game_target) > 10.0 or attempts > 5: break
            attempts += 1
            
        self.game_target = new_target
        self.target_assigned_time = now_ts
        self.match_start_time = None
        
        self.logger.log(f"GAME: New Target {self.game_target:.1f} BPM! Match it!")
