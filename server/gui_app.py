import threading
from queue import SimpleQueue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- Mock imports for context ---
try:
    from session_runner import create_session, run_session_loop
    from BPM_estimation import BPM_estimation
    from plotter import _elapsed_to_seconds, LivePlotter, generate_post_session_plot
    from main import main as run_main_logic
except ImportError:
    pass

try:
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# ==================================================================================
# LOGIC CLASS (Unchanged)
# ==================================================================================

# ==================================================================================
# THREADING & LOGIC BRIDGE
# This class runs the music/serial loop in the background so the GUI doesn't freeze.
# ==================================================================================

class SessionThread(threading.Thread):
    """
    Background worker thread. 
    It imports and runs 'session_runner' logic in a separate process flow.
    It communicates back to the GUI using callbacks.
    """
    def __init__(self, midi_path, serial_port, manual_mode, manual_bpm, log_callback, session_dir_callback):
        super().__init__(daemon=True) # Daemon means it dies when the main app closes
        self.midi_path = midi_path
        self.serial_port = serial_port
        self.manual_mode = manual_mode
        self.manual_bpm = manual_bpm
        self.log_callback = log_callback # Function to send text back to GUI
        self.session_dir_callback = session_dir_callback # Function to send file path back
        self.stop_event = threading.Event()
        self.bpm_est = None
        self._pending_bpm = manual_bpm
        self._pending_manual_mode = manual_mode

    def _log(self, msg):
        if self.log_callback: self.log_callback(msg)

    def update_manual_bpm(self, bpm):
        self._pending_bpm = bpm
        if self.bpm_est: self.bpm_est.set_manual_bpm(bpm)

    def set_manual_mode(self, enabled):
        self._pending_manual_mode = enabled
        if self.bpm_est: self.bpm_est.set_manual_mode(enabled)

    def set_manual_mode(self, enabled):
        self._pending_manual_mode = enabled
        if self.bpm_est: self.bpm_est.set_manual_mode(enabled)
        
    def update_smoothing_alpha(self, alpha):
        if self.bpm_est: self.bpm_est.set_smoothing_alpha(alpha)

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            self._log("Loading MIDI & Session...")
            from main import main as run_main_logic
            from types import SimpleNamespace
            
            # Create a mock ARGS object to pass to main()
            args = SimpleNamespace(
                midi_path=self.midi_path,
                manual=self.manual_mode,
                bpm=self.manual_bpm,
                serial_port=self.serial_port
            )
            
            # Run the logic from main.py
            # We capture the returns (player, logger, bpm_est) so we can update them manually if needed
            _, _, self.bpm_est = run_main_logic(
                args, 
                status_callback=self.log_callback,
                stop_event=self.stop_event,
                session_dir_callback=self.session_dir_callback
            )

        except Exception as exc:
            self._log(f"Error: {exc}")
        finally:
            self._log("Session ended.")

# ==================================================================================
# GUI CLASS
# ==================================================================================

# ==================================================================================
# MAIN GUI APPLICATION
# This class handles the window, buttons, and layout using Tkinter.
# ==================================================================================

class GuiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Brain-Music Interface")
        root.geometry("1100x850")
        
        # --- THEME CONFIGURATION ---
        # Defines the Slate/Dark color palette for a modern look.
        self.P = {
            "bg": "#0f172a", "card_bg": "#1e293b", "input_bg": "#334155",
            "text_main": "#f8fafc", "text_sub": "#94a3b8",
            "accent": "#3b82f6", "accent_hover": "#2563eb",
            "danger": "#ef4444", "success": "#22c55e", "warning": "#eab308",
            "border": "#334155",
        }
        # TWEAK: To change the background color, edit "bg" above.
        # TWEAK: To change the button color, edit "accent" above.
        root.configure(bg=self.P["bg"])

        # --- STYLE SETUP ---
        # ttk.Style allows us to customize how buttons and labels look globally.
        style = ttk.Style()
        try: style.theme_use("clam")
        except: pass
        style.configure(".", background=self.P["bg"], foreground=self.P["text_main"], font=("Segoe UI", 10))
        style.configure("TFrame", background=self.P["bg"])
        style.configure("Card.TFrame", background=self.P["card_bg"], relief="flat")
        style.configure("H1.TLabel", font=("Segoe UI", 18, "bold"), foreground=self.P["text_main"], background=self.P["bg"])
        style.configure("CardHeader.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.P["text_sub"], background=self.P["card_bg"])
        style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground=self.P["text_sub"], background=self.P["bg"])
        style.configure("CardLabel.TLabel", background=self.P["card_bg"], foreground=self.P["text_main"])
        style.configure("NavStatus.TLabel", background=self.P["bg"], foreground=self.P["accent"], font=("Segoe UI", 9, "italic"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=self.P["accent"], foreground="white", borderwidth=0, focuscolor=self.P["accent"], padding=(15, 10))
        style.map("Primary.TButton", background=[("active", self.P["accent_hover"])])
        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), background=self.P["danger"], foreground="white", borderwidth=0, padding=(15, 10))
        style.map("Danger.TButton", background=[("active", "#b91c1c")])
        style.configure("Secondary.TButton", font=("Segoe UI", 10, "bold"), background=self.P["input_bg"], foreground=self.P["text_main"], borderwidth=0, padding=(15, 10))
        style.map("Secondary.TButton", background=[("active", "#475569")])
        style.configure("Compact.TButton", background=self.P["input_bg"], foreground=self.P["text_main"], borderwidth=0, padding=(8, 4))
        style.configure("TEntry", fieldbackground=self.P["input_bg"], foreground=self.P["text_main"], padding=5, borderwidth=0)
        style.configure("TRadiobutton", background=self.P["card_bg"], foreground=self.P["text_main"], font=("Segoe UI", 10))
        style.map("TRadiobutton", indicatorcolor=[("selected", self.P["accent"])], background=[("active", self.P["card_bg"])])

        base_dir = Path(__file__).resolve().parent.parent
        default_midi = base_dir / "midi_files" / "Technion_March1.mid"
        
        self.session_thread = None
        self.status_queue = SimpleQueue()
        self.session_dir_queue = SimpleQueue()
        self.current_session_dir = None
        self.is_running = False

        # --- LAYOUT ---
        navbar = ttk.Frame(root, style="TFrame")
        navbar.pack(fill="x", padx=25, pady=(20, 10))
        
        title_box = ttk.Frame(navbar, style="TFrame")
        title_box.pack(side="left")
        ttk.Label(title_box, text="⚡ BRAIN SYNC", style="H1.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Neuro-Adaptive Music Controller", style="Sub.TLabel").pack(anchor="w")
        
        status_box = ttk.Frame(navbar, style="TFrame")
        status_box.pack(side="right", anchor="e")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_box, textvariable=self.status_var, style="NavStatus.TLabel").pack(side="left", padx=(0, 15))
        self.led_canvas = tk.Canvas(status_box, width=100, height=30, bg=self.P["bg"], highlightthickness=0)
        self.led_canvas.pack(side="left")
        self.led_sys = self._draw_led(80, 15, "System", self.P["success"])
        self.led_run = self._draw_led(20, 15, "Active", self.P["input_bg"])
        
        main_body = ttk.Frame(root, style="TFrame")
        main_body.pack(fill="both", expand=True, padx=25, pady=10)
        main_body.columnconfigure(0, weight=0, minsize=340)
        main_body.columnconfigure(1, weight=1)
        main_body.rowconfigure(0, weight=1)

        # SIdebar
        sidebar = ttk.Frame(main_body, style="Card.TFrame", padding=20)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        def section(title): ttk.Label(sidebar, text=title.upper(), style="CardHeader.TLabel").pack(anchor="w", pady=(15, 8))

        section("Configuration")
        ttk.Label(sidebar, text="MIDI Track", style="CardLabel.TLabel").pack(anchor="w")
        self.midi_var = tk.StringVar(value=str(default_midi))
        midi_row = ttk.Frame(sidebar, style="Card.TFrame")
        midi_row.pack(fill="x", pady=(5, 15))
        ttk.Entry(midi_row, textvariable=self.midi_var).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(midi_row, text="📂", style="Compact.TButton", width=3, command=self.choose_midi).pack(side="right")

        # Serial Port Setup
        ttk.Label(sidebar, text="Serial Port", style="CardLabel.TLabel").pack(anchor="w")
        port_row = ttk.Frame(sidebar, style="Card.TFrame")
        port_row.pack(fill="x", pady=(5, 0))
        
        self.port_var = tk.StringVar(value="COM3") # Default
        
        if SERIAL_AVAILABLE:
            self.port_combo = ttk.Combobox(port_row, textvariable=self.port_var)
            self.port_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
            ttk.Button(port_row, text="🔄", style="Compact.TButton", width=4, command=self.refresh_ports).pack(side="right")
            self.refresh_ports() 
        else:
            # Fallback to text entry if pyserial not installed
            ttk.Entry(port_row, textvariable=self.port_var).pack(fill="x", expand=True)

        section("Sync Mode")
        self.mode_var = tk.StringVar(value="dynamic")
        ttk.Radiobutton(sidebar, text="🧠 Dynamic", value="dynamic", variable=self.mode_var, command=self.on_mode_change).pack(anchor="w", pady=5)
        ttk.Radiobutton(sidebar, text="🛠 Manual Override", value="manual", variable=self.mode_var, command=self.on_mode_change).pack(anchor="w", pady=5)
        # MANUAL BPM
        self.manual_bpm_frame = ttk.Frame(sidebar, style="Card.TFrame")
        self.manual_bpm_frame.pack(fill="x", pady=10)
        
        ttk.Label(self.manual_bpm_frame, text="Target BPM", style="CardHeader.TLabel").pack(anchor="w")
        
        bpm_row = ttk.Frame(self.manual_bpm_frame, style="Card.TFrame")
        bpm_row.pack(fill="x", pady=5)
        
        self.manual_bpm_var = tk.StringVar(value="100")
        self.bpm_entry = ttk.Entry(bpm_row, textvariable=self.manual_bpm_var, width=6)
        self.bpm_entry.pack(side="left", padx=(0, 5))
        
        self.btn_set_bpm = tk.Button(bpm_row, text="Set", font=("Segoe UI", 9, "bold"),
                  bg=self.P["accent"], fg="white", activebackground=self.P["accent_hover"],
                  relief="flat", padx=10, command=self.apply_manual_bpm)
        self.btn_set_bpm.pack(side="left")

        # SMOOTHING CONTROL
        ttk.Label(sidebar, text="Decay Speed (Smoothing)", style="CardHeader.TLabel").pack(anchor="w", pady=(15, 0))
        
        smoothing_row = ttk.Frame(sidebar, style="Card.TFrame")
        smoothing_row.pack(fill="x", pady=5)
        
        self.smoothing_var = tk.StringVar(value="0.05")
        self.smoothing_entry = ttk.Entry(smoothing_row, textvariable=self.smoothing_var, width=6)
        self.smoothing_entry.pack(side="left", padx=(0, 5))
        
        tk.Button(smoothing_row, text="Set", font=("Segoe UI", 9, "bold"),
                  bg=self.P["accent"], fg="white", activebackground=self.P["accent_hover"],
                  relief="flat", padx=10, command=self.apply_smoothing).pack(side="left")

        tk.Button(smoothing_row, text="?", font=("Segoe UI", 9, "bold"),
                  bg=self.P["card_bg"], fg=self.P["accent"], activebackground=self.P["card_bg"],
                  relief="flat", padx=5, command=self.show_smoothing_help).pack(side="left", padx=5)
        
        # --- BOTTOM CONTROLS ---
        ttk.Frame(sidebar, style="Card.TFrame").pack(fill="both", expand=True) # Spacer pushes everything down

        section("Session Control")
        self.btn_start = ttk.Button(sidebar, text="▶ START SESSION", command=self.start_session, style="Primary.TButton")
        self.btn_start.pack(fill="x", pady=(0, 10))
        
        self.btn_stop = ttk.Button(sidebar, text="⏹ STOP SESSION", command=self.stop_session, style="Danger.TButton", state="disabled")
        self.btn_stop.pack(fill="x", pady=(0, 10))

        self.btn_quit = ttk.Button(sidebar, text="❌ QUIT APP", command=self.quit_app, style="Secondary.TButton")
        self.btn_quit.pack(fill="x")

        # Visualization
        viz_root = ttk.Frame(main_body, style="TFrame")
        viz_root.grid(row=0, column=1, sticky="nsew")
        plot_card = ttk.Frame(viz_root, style="Card.TFrame", padding=10)
        plot_card.pack(fill="both", expand=True)
        
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.figure.patch.set_facecolor(self.P["card_bg"])
        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212, sharex=self.ax1)
        self.figure.subplots_adjust(left=0.08, bottom=0.1, right=0.95, top=0.92, hspace=0.3)
        
        # Initialize Plotter Logic
        self.plotter = LivePlotter(self.ax1, self.ax2, self.P)
        # Initial style application (empty)
        self.plotter.update(pd.DataFrame({"seconds": [], "walking_bpm": [], "song_bpm": [], "step_event": []}))

        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.on_mode_change() # Init state
        self.poll_status()
        self.poll_session_dir()
        self.poll_plot()

    def _draw_led(self, x, y, l, c):
        r=6; o=self.led_canvas.create_oval(x-r, y-r, x+r, y+r, fill=c, outline="")
        self.led_canvas.create_text(x+15, y, text=l, anchor="w", fill=self.P["text_sub"], font=("Segoe UI", 9))
        return o

    def _set_led(self, i, a, c=None): self.led_canvas.itemconfig(i, fill=(c if c else self.P["success"]) if a else self.P["input_bg"])

    def log(self, msg): self.status_var.set(msg)
    def choose_midi(self): 
        p = filedialog.askopenfilename(filetypes=[("MIDI", ".mid"), ("All", ".*")])
        if p: self.midi_var.set(p)

    def refresh_ports(self):
        """Populate the combobox with detected serial ports."""
        if not SERIAL_AVAILABLE: return
        ports = serial.tools.list_ports.comports()
        values = [f"{p.device} - {p.description}" for p in ports]
        self.port_combo['values'] = values
        if values:
            self.port_combo.current(0)
        else:
            self.port_combo.set("No devices found")

    def get_selected_port(self):
        """Extract just the COM port from the selection string 'COM3 - Arduino Uno'."""
        val = self.port_var.get()
        if " - " in val:
            return val.split(" - ")[0]
        return val

    # --- CALLBACKS & UI UPDATES ---
    
    def on_mode_change(self):
        """Called when user clicks Dynamic/Manual radio buttons."""
        manual = self.mode_var.get() == "manual"
        
        # If session is running, update it in real-time
        if self.session_thread: self.session_thread.set_manual_mode(manual)
        
        # Toggle UI Controls (Enable/Disable BPM input)
        s = "normal" if manual else "disabled"
        self.bpm_entry.configure(state=s)
        self.btn_set_bpm.configure(state=s)
        self.log(f"Mode: {'Manual' if manual else 'Dynamic'}")

    def start_session(self):
        """Action for the 'START SESSION' button."""
        if self.is_running: return
        p = Path(self.midi_var.get())
        if not p.exists(): messagebox.showerror("Error", "MIDI not found"); return
        
        port = self.get_selected_port()
        if not port or "No devices" in port:
            messagebox.showerror("Error", "Please select a valid Serial Port")
            return

        # Prepare parameters
        mm = self.mode_var.get() == "manual"
        mb = self._parse_bpm(self.manual_bpm_var.get()) if mm else None
        
        # Create and start the background thread
        self.session_thread = SessionThread(str(p), port, mm, mb, self.enqueue_status, self.enqueue_session_dir)
        self.session_thread.start()
        
        # Update UI state
        self.is_running = True
        self.btn_start.configure(state="disabled"); self.btn_stop.configure(state="normal")
        self._set_led(self.led_run, True, self.P["warning"]); self.log(f"Session running on {port}")

    def stop_session(self):
        """Action for the 'STOP SESSION' button."""
        if self.session_thread: self.session_thread.stop()
        self.is_running = False
        self.btn_start.configure(state="normal"); self.btn_stop.configure(state="disabled")
        self._set_led(self.led_run, False); self.log("Stopped")
        
        # Generate Post-Session Plot
        if self.current_session_dir:
            try:
                self.log("Generating plot...")
                generate_post_session_plot(self.current_session_dir)
                self.log(f"Saved plot to {self.current_session_dir.name}")
            except Exception as e:
                self.log(f"Plot failed: {e}")

    def apply_manual_bpm(self):
        b = self._parse_bpm(self.manual_bpm_var.get())
        if b:
            if self.session_thread: self.session_thread.update_manual_bpm(b)
            self.mode_var.set("manual"); self.log(f"Manual BPM: {b}")
        else: messagebox.showerror("Error", "Invalid BPM")

    def apply_smoothing(self):
        try:
            val = float(self.smoothing_var.get())
            if val < 0.001 or val > 1.0: raise ValueError
            if self.session_thread: self.session_thread.update_smoothing_alpha(val)
            self.log(f"Smoothing set to {val}")
        except ValueError:
            messagebox.showerror("Error", "Invalid number. Use 0.001 - 1.0")

    def show_smoothing_help(self):
        msg = ("Controls how fast the music slows down when you stop walking.\n\n"
               "0.01 = Very slow, cinematic decay.\n"
               "0.20 = Fast, responsive decay.\n"
               "1.00 = Instant (robotic).\n\n"
               "Recommended: 0.05")
        messagebox.showinfo("Smoothing Factor", msg)

    def quit_app(self):
        """Cleanly exit the application."""
        if self.session_thread: self.session_thread.stop()
        self.root.quit()
        self.root.destroy()

    # --- POLLING LOOPS ---
    # Tkinter isn't thread-safe, so we check Queues for messages from the background thread.
    
    def enqueue_status(self, m): self.status_queue.put(m)
    def enqueue_session_dir(self, p): self.session_dir_queue.put(p)
    
    def poll_status(self):
        """Checks for new status messages every 200ms."""
        while not self.status_queue.empty(): self.log(self.status_queue.get_nowait())
        self.root.after(200, self.poll_status)
        
    def poll_session_dir(self):
        """Checks if a new session folder was created."""
        while not self.session_dir_queue.empty():
            self.current_session_dir = self.session_dir_queue.get_nowait()
            self.log(f"Logging: {self.current_session_dir.name}")
        self.root.after(500, self.poll_session_dir)
        
    def poll_plot(self):
        """Updates the graph every 100ms."""
        # TWEAK: Change '100' below to make the graph faster (e.g. 50) or slower (e.g. 500).
        # Lower numbers = smoother but more CPU usage.
        if self.current_session_dir: self.refresh_plot()
        self.root.after(100, self.poll_plot) # Ultra-fast refresh (100ms)

    def refresh_plot(self):
        """Reads CSV and calls the plotter (visual logic is in plotter.py)."""
        c = self.current_session_dir / "session_data.csv"
        if not c.exists(): return
        try:
            # We use pandas to read the CSV quickly
            df = pd.read_csv(c)
            if df.empty or "time" not in df.columns: return
            if 'seconds' not in df.columns: df["seconds"] = df.index
            if "step_event" not in df.columns: df["step_event"] = False
            else: df["step_event"] = df["step_event"].astype(str).str.lower().isin(["true", "1", "yes"])
        except: return
        
        # Delegate to Plotter
        self.plotter.update(df)
        self.figure.tight_layout(); self.canvas.draw_idle()

    @staticmethod
    def _parse_bpm(v):
        try: return float(v) if float(v)>0 else None
        except: return None

def main():
    root = tk.Tk()
    try: from ctypes import windll; windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    GuiApp(root)
    root.mainloop()

if __name__ == "__main__": main()
