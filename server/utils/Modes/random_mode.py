import random
from utils.Modes.base_mode import BaseMode

class RandomMode(BaseMode):
    def __init__(self, context):
        super().__init__(context)
        # Game State
        self.game_target = None
        self.target_assigned_time = None
        self.match_start_time = None
        
        # Simple Mode State
        self.matched_step_counter = 0

        # Configuration
        self.span = 0.20 # Default 20%
        self.gamified = True # Default to Game Mode

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

    def on_step(self, bpm):
        """Called on every step."""
        if self.gamified or self.game_target is None:
             return
             
        # Simple Mode Step Logic
        THRESHOLD = 5.0
        STEPS_TO_HOLD = 20
        
        diff = abs(bpm - self.game_target)
        if diff < THRESHOLD:
            self.matched_step_counter += 1
            if self.matched_step_counter % 5 == 0: 
                 self.logger.log(f"SIMPLE: Matched {self.matched_step_counter}/{STEPS_TO_HOLD} steps...")
                 
            if self.matched_step_counter >= STEPS_TO_HOLD:
                 self.logger.log(f"SIMPLE: Completed {STEPS_TO_HOLD} steps! Next target.")
                 self._pick_new_target(self.context.last_update_time)
                 self.matched_step_counter = 0
        else:
            # If they lose sync, do we reset? 
            # User said "wait for user to match", usually implies cumulative or continuous.
            # I'll reset to require *continuous* matching for stability.
            if self.matched_step_counter > 0:
                 self.logger.log("SIMPLE: Lost match. Resetting counter.")
            self.matched_step_counter = 0

    def handle_step(self, now_ts, current_bpm):
        """
        Orchestrates Random Mode (Gamified or Simple).
        """
        # 1. Initialization
        if self.game_target is None:
            self._pick_new_target(now_ts)
            return self.game_target
            
        # --- SIMPLE MODE ---
        if not self.gamified:
             # Logic is handled in on_step()
             # We just return the target
             return self.game_target

        # --- GAMIFIED MODE ---
        TIMEOUT_DURATION = 20.0
        HOLD_DURATION = 10.0
        THRESHOLD = 5.0
        
        # 2. Timeout Check
        if self.target_assigned_time and (now_ts - self.target_assigned_time > TIMEOUT_DURATION):
             self.logger.log(f"GAME: Timeout ({TIMEOUT_DURATION}s)! Skipping...")
             self._pick_new_target(now_ts)
             return self.game_target

        # 3. Match & Hold Check
        diff = abs(current_bpm - self.game_target)

        # Matched?
        if diff < THRESHOLD:
            if self.match_start_time is None:
                self.match_start_time = now_ts
                self.logger.log("GAME: Matched! Hold it...")
            
            # Held long enough?
            held_duration = now_ts - self.match_start_time
            if held_duration > HOLD_DURATION:
                self.logger.log(f"GAME: Success! Held for {HOLD_DURATION}s.")
                self._pick_new_target(now_ts)
        else:
            # Lost the match
            if self.match_start_time is not None:
                self.logger.log("GAME: Lost match! Try again.")
                self.match_start_time = None
        
        return self.game_target

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
