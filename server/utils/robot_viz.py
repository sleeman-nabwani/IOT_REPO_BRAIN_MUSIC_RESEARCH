import tkinter as tk
import math
import time
import os

class RobotVisualizer:
    def __init__(self, parent, theme, width=200, height=300):
        self.P = theme
        self.width = width
        self.height = height
        
        # Container frame
        self.frame = tk.Frame(parent, bg=self.P["card_bg"], width=width, height=height)
        self.frame.pack_propagate(False) # Fixed size
        self.frame.pack(fill="both", expand=True)
        
        # Canvas
        self.canvas = tk.Canvas(self.frame, width=width, height=height, bg=self.P["card_bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # State
        self.bpm = 0.0
        self.target_bpm = 0.0
        self.phase = 0.0
        self.last_time = time.time()
        self.running = True
        
        self.sprites = []
        self._load_assets()
        
        self.particles = []
        self.floor_offset = 0.0
        
        # Drawing Elements
        self.parts = {}
        self._init_scene()
        
        # Start Animation Loop
        self._animate()
        
    def _load_assets(self):
        """Loads sprite frames."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # server
        assets_dir = os.path.join(base_dir, "assets")
        
        try:
            for i in range(4):
                path = os.path.join(assets_dir, f"sonic_run_{i}.png")
                if os.path.exists(path):
                    img = tk.PhotoImage(file=path)
                    # Check size and scale if needed
                    # If image is > 200px wide, scale down
                    if img.width() > self.width:
                        # Simple subsample (integer scaling)
                        factor = int(img.width() / self.width) + 1
                        img = img.subsample(factor, factor)
                    
                    self.sprites.append(img)
                else:
                    print(f"Warning: Sprite {path} not found.")
        except Exception as e:
            print(f"Error loading sprites: {e}")

    def _init_scene(self):
        self.canvas.delete("all")
        cx, cy = self.width / 2, self.height / 2
        
        # Background Floor (Checkerboard or Striped)
        # We draw lines that we can move
        self.parts['bg_lines'] = []
        for i in range(10):
            x = i * 40
            l = self.canvas.create_line(x, self.height-20, x+20, self.height-20, width=4, fill="#475569")
            self.parts['bg_lines'].append(l)

        # Image holder
        if self.sprites:
            # Create image item. center anchor.
            self.parts['sprite'] = self.canvas.create_image(cx, cy, image=self.sprites[0], anchor="center")
        else:
            self.parts['sprite'] = None
            self.canvas.create_text(cx, cy, text="Loading Sprites...", fill="white")

        # Text Overlay
        self.parts['bpm_text'] = self.canvas.create_text(cx, self.height-30, text="0 BPM", fill="white", font=("Segoe UI", 14, "bold"))
        self.parts['flash'] = self.canvas.create_rectangle(0,0, self.width, self.height, fill="white", state="hidden") # Flash effect

    def update_bpm(self, bpm):
        self.target_bpm = bpm
        self.canvas.itemconfig(self.parts['bpm_text'], text=f"{int(bpm)} BPM")
        
    def trigger_step(self):
        """Called when a real footstep is detected via sensor."""
        self._flash_screen()
        # Reset phase to 0.0 (Contact)
        self.phase = 0.0
        
        # Burst of particles
        cx, cy = self.width / 2, self.height / 2
        for _ in range(3):
            self.particles.append({
                'id': self.canvas.create_oval(0,0,0,0, fill="#e2e8f0", outline=""),
                'x': cx - 20, # Behind feet
                'y': cy + 60, # Ground level (approx)
                'vx': -2.0 - (self.bpm/20.0), # Move left fast
                'vy': -1.0 - (self.bpm/50.0), # Up slightly
                'life': 1.0
            })
        
    def _flash_screen(self):
        self.canvas.configure(bg="#334155")
        self.frame.after(50, lambda: self.canvas.configure(bg=self.P["card_bg"]))

    def _animate(self):
        if not self.running: return
        
        dt = time.time() - self.last_time
        self.last_time = time.time()
        
        # Smooth BPM
        diff = self.target_bpm - self.bpm
        if abs(diff) > 1.0: self.bpm += diff * 5.0 * dt
        else: self.bpm = self.target_bpm
            
        cx, cy = self.width / 2, self.height / 2
        
        # --- ANIMATE SCENE ---
        if self.bpm > 5:
            # Scroll Floor
            # Speed px/sec proportional to BPM
            scroll_speed = self.bpm * 2.0 # e.g. 100 BPM -> 200px/s
            self.floor_offset -= scroll_speed * dt
            self.floor_offset %= 80 # Repeat every 80px (approx 2 lines)
            
            for i, l in enumerate(self.parts['bg_lines']):
                base_x = (i * 80) + self.floor_offset
                # Wrap
                if base_x < -40: base_x += 800
                self.canvas.coords(l, base_x, self.height-10, base_x+40, self.height-10)

            # Particles
            dead = []
            for p in self.particles:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['life'] -= dt * 2.0 # Fade speed
                
                size = p['life'] * 10
                self.canvas.coords(p['id'], p['x'], p['y'], p['x']+size, p['y']+size)
                
                if p['life'] <= 0:
                    self.canvas.delete(p['id'])
                    dead.append(p)
            for p in dead: self.particles.remove(p)

        if self.sprites and self.parts['sprite']:
            if self.bpm > 10:
                # RUNNING
                cps = self.bpm / 60.0
                self.phase += cps * 2 * math.pi * dt
                self.phase %= (2 * math.pi)
                
                # Map 0-2PI to 0-4 frames
                frame_idx = int((self.phase / (2*math.pi)) * len(self.sprites))
                frame_idx = frame_idx % len(self.sprites)
                
                img = self.sprites[frame_idx]
                self.canvas.itemconfig(self.parts['sprite'], image=img)
                
                # Bobbing Effect WITH SQUASH (simulated via Y offset mainly)
                # Bob down on Contact (Phase 0 and PI)
                # Bob up on Flight (Phase PI/2 and 3PI/2)
                bob = -abs(math.sin(self.phase)) * 8 # Bobs UP (negative Y)
                
                # Lean forward with speed
                lean = (self.bpm / 200.0) * 10
                
                self.canvas.coords(self.parts['sprite'], cx + lean, cy + 20 + bob) # +20 to ground align

            else:
                # IDLE
                self.canvas.itemconfig(self.parts['sprite'], image=self.sprites[0])
                self.canvas.coords(self.parts['sprite'], cx, cy + 20)
                self.phase = 0

        self.frame.after(33, self._animate)
        
    def stop(self):
        self.running = False
