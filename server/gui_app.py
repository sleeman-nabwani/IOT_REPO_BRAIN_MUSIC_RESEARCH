import threading
from queue import SimpleQueue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# --- Mock imports for context ---
try:
    from utils.plotter import _elapsed_to_seconds, LivePlotter, generate_post_session_plot
    from utils.process_manager import SubprocessManager
except ImportError:
    pass


try:
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# ==================================================================================
# GUI APPLICATION
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
            "bg": "#0f172a", "card_bg": "#1e293b", "input_bg": "#f1f5f9", # Light BG for inputs
            "text_main": "#f8fafc", "text_sub": "#94a3b8", "text_input": "#0f172a", # Black/Dark text for inputs
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
        style.configure("CardHeader.TLabel", font=("Segoe UI", 12, "bold"), foreground=self.P["text_sub"], background=self.P["card_bg"])
        style.configure("Sub.TLabel", font=("Segoe UI", 11), foreground=self.P["text_sub"], background=self.P["bg"])
        style.configure("CardLabel.TLabel", background=self.P["card_bg"], foreground=self.P["text_main"])
        style.configure("NavStatus.TLabel", background=self.P["bg"], foreground=self.P["accent"], font=("Segoe UI", 9, "italic"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=self.P["accent"], foreground="white", borderwidth=0, focuscolor=self.P["accent"], padding=(15, 10))
        style.map("Primary.TButton", background=[("active", self.P["accent_hover"])])
        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), background=self.P["danger"], foreground="white", borderwidth=0, padding=(15, 10))
        style.map("Danger.TButton", background=[("active", "#b91c1c")])
        # CHANGED: Gray button for Quit (User Request)
        style.configure("Secondary.TButton", font=("Segoe UI", 10, "bold"), background="#64748b", foreground="white", borderwidth=0, padding=(15, 10))
        style.map("Secondary.TButton", background=[("active", "#475569")])
        style.configure("Compact.TButton", background=self.P["input_bg"], foreground=self.P["text_input"], borderwidth=0, padding=(8, 4))
        # INPUTS: Light BG, Dark Text
        style.configure("TEntry", fieldbackground=self.P["input_bg"], foreground=self.P["text_input"], padding=5, borderwidth=0)
        style.configure("TCombobox", fieldbackground=self.P["input_bg"], foreground=self.P["text_input"], background=self.P["input_bg"])
        style.map("TCombobox", fieldbackground=[("readonly", self.P["input_bg"])], foreground=[("readonly", self.P["text_input"])])
        
        style.configure("TRadiobutton", background=self.P["card_bg"], foreground=self.P["text_main"], font=("Segoe UI", 10))
        style.map("TRadiobutton", indicatorcolor=[("selected", self.P["accent"])], background=[("active", self.P["card_bg"])])

        # NEW: Compact Blue Button for "Set"
        style.configure("CompactPrimary.TButton", font=("Segoe UI", 9, "bold"), background=self.P["accent"], foreground="white", borderwidth=0, padding=(8, 4))
        style.map("CompactPrimary.TButton", background=[("active", self.P["accent_hover"])])
        
        # New: Help Button Style (Ghost)
        style.configure("Help.TButton", font=("Segoe UI", 9, "bold"), background=self.P["card_bg"], foreground=self.P["accent"], borderwidth=0, padding=(2, 0))
        style.map("Help.TButton", background=[("active", self.P["card_bg"])], foreground=[("active", "white")])

        base_dir = Path(__file__).resolve().parent.parent
        default_midi = base_dir / "midi_files" / "Technion_March1.mid"
        
        self.session_thread = None
        self.status_queue = SimpleQueue()
        self.session_dir_queue = SimpleQueue()
        self.data_queue = SimpleQueue()
        self.current_session_dir = None
        self.live_data_buffer = []
        # Limit how many recent points are kept/rendered to avoid UI lag
        self.max_live_points = 2000  # smaller window for smoother Tk/Matplotlib
        self.is_running = False
        self.is_app_active = True
        
        # Poll jobs
        self.job_status = None
        self.job_dir = None
        self.job_plot = None
        self.job_ports = None



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

        # SIdebar Container (Holds Canvas + Scrollbar)
        sidebar_container = ttk.Frame(main_body, style="Card.TFrame")
        sidebar_container.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        # Create Canvas & Scrollbar
        self.canvas_sidebar = tk.Canvas(sidebar_container, bg=self.P["card_bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical", command=self.canvas_sidebar.yview)
        
        # The actual Frame inside the canvas
        sidebar = ttk.Frame(self.canvas_sidebar, style="Card.TFrame", padding=20)
        
        # Logic to make the frame inside the canvas scrollable
        sidebar.bind(
            "<Configure>",
            lambda e: self.canvas_sidebar.configure(
                scrollregion=self.canvas_sidebar.bbox("all")
            )
        )
        
        self.canvas_sidebar.create_window((0, 0), window=sidebar, anchor="nw", tags="inner_frame")
        self.canvas_sidebar.configure(yscrollcommand=scrollbar.set)
        
        self.canvas_sidebar.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mousewheel Binding (Windows/Linux)
        def _on_mousewheel(event):
            self.canvas_sidebar.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel only when hovering over sidebar
        self.canvas_sidebar.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Fix width of inner frame to match canvas
        def _configure_canvas(event):
            self.canvas_sidebar.itemconfig("inner_frame", width=event.width)
        self.canvas_sidebar.bind("<Configure>", _configure_canvas)
        
        def section(title): ttk.Label(sidebar, text=title.upper(), style="CardHeader.TLabel").pack(anchor="w", pady=(15, 8))
        
        # ANALYSIS SECTION
        section("Analysis")
        # Row 1: Subject Folder
        self.analysis_row1 = ttk.Frame(sidebar, style="Card.TFrame")
        self.analysis_row1.pack(fill="x", pady=(0, 2))
        
        self.subject_var = tk.StringVar()
        self.subject_combo = ttk.Combobox(self.analysis_row1, textvariable=self.subject_var, state="readonly", height=15)
        self.subject_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.subject_combo.bind("<<ComboboxSelected>>", self.on_subject_selected)
        
        ttk.Button(self.analysis_row1, text="🔄", style="Compact.TButton", width=3, command=self.refresh_analysis_subjects).pack(side="right")

        # Row 2: Session List + View Button
        self.analysis_row2 = ttk.Frame(sidebar, style="Card.TFrame")
        self.analysis_row2.pack(fill="x", pady=(0, 5))
        
        self.session_var = tk.StringVar()
        self.session_combo = ttk.Combobox(self.analysis_row2, textvariable=self.session_var, state="readonly", height=15)
        self.session_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(self.analysis_row2, text="📊", style="Compact.TButton", width=3, command=self.view_session_plot).pack(side="right")

        # MIDI Track Selection
        ttk.Label(sidebar, text="MIDI TRACK", style="CardHeader.TLabel").pack(anchor="w")
        self.midi_var = tk.StringVar(value=str(default_midi.name)) # Just name for dropdown
        midi_row = ttk.Frame(sidebar, style="Card.TFrame")
        midi_row.pack(fill="x", pady=(5, 15))
        
        self.midi_combo = ttk.Combobox(midi_row, textvariable=self.midi_var)
        self.midi_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        # Folder button to open directory or pick file? 
        # User wants dropdown, maybe keep "Open" button to pick custom?
        # Let's keep one folder button to Pick Custom File.
        ttk.Button(midi_row, text="📂", style="Compact.TButton", width=3, command=self.choose_midi).pack(side="right")
        
        # SESSION NAME SELECTOR
        ttk.Label(sidebar, text="SESSION NAME (LOG FILE)", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        self.session_row = ttk.Frame(sidebar, style="Card.TFrame")
        self.session_row.pack(fill="x", pady=(5, 10))
        
        self.session_name_var = tk.StringVar()
        # Initial widget (will be updated by refresh)
        self.session_input_widget = ttk.Combobox(self.session_row, textvariable=self.session_name_var)
        self.session_input_widget.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        ttk.Button(self.session_row, text="🔄", style="Compact.TButton", width=4, command=self.refresh_session_list).pack(side="right") # Refresh list
        ttk.Label(sidebar, text="SERIAL PORT", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        port_row = ttk.Frame(sidebar, style="Card.TFrame")
        port_row.pack(fill="x", pady=(5, 0))
        
        self.port_var = tk.StringVar(value="COM3") # Default
        
        if SERIAL_AVAILABLE:
            self.port_combo = ttk.Combobox(port_row, textvariable=self.port_var)
            self.port_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
            # No manual refresh needed anymore, but keeping button just in case
            ttk.Button(port_row, text="🔄", style="Compact.TButton", width=4, command=self.refresh_ports).pack(side="right")
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
        
        # BPM Slider
        self.manual_bpm_var = tk.DoubleVar(value=100.0)
        
        bpm_row = ttk.Frame(self.manual_bpm_frame, style="Card.TFrame")
        bpm_row.pack(fill="x", pady=5)
        
        self.bpm_val_label = ttk.Label(bpm_row, text="100 BPM", style="Sub.TLabel", width=10)
        self.bpm_val_label.pack(side="right", padx=5)

        self.bpm_slider = ttk.Scale(bpm_row, from_=0, to=400, orient="horizontal", 
                                   variable=self.manual_bpm_var, command=self.on_bpm_slider_change)
        self.bpm_slider.pack(side="left", fill="x", expand=True, padx=5)

        # SMOOTHING CONTROL (Climbing & Cascading)
        ttk.Label(sidebar, text="CLIMBING (SPEEDING UP)", style="CardHeader.TLabel").pack(anchor="w", pady=(15, 0))
        
        attack_row = ttk.Frame(sidebar, style="Card.TFrame")
        attack_row.pack(fill="x", pady=5)
        
        self.smoothing_up_var = tk.StringVar() 
        entry_up = ttk.Entry(attack_row, textvariable=self.smoothing_up_var, width=15, font=("Segoe UI", 12))
        entry_up.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_up, self.smoothing_up_var, "Set Climbing")
        
        ttk.Button(attack_row, text="?", style="Help.TButton", width=2, command=self.show_attack_help).pack(side="left", padx=5)

        # Cascading
        ttk.Label(sidebar, text="CASCADING (SLOWING DOWN)", style="CardHeader.TLabel").pack(anchor="w", pady=(15, 0))
        
        decay_row = ttk.Frame(sidebar, style="Card.TFrame")
        decay_row.pack(fill="x", pady=5)
        
        self.smoothing_down_var = tk.StringVar()
        entry_down = ttk.Entry(decay_row, textvariable=self.smoothing_down_var, width=15, font=("Segoe UI", 12))
        entry_down.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_down, self.smoothing_down_var, "Set Cascading")

        ttk.Button(decay_row, text="?", style="Help.TButton", width=2, command=self.show_decay_help).pack(side="left", padx=5)

        # STEP AVERAGING WINDOW (ESP32 Config)
        ttk.Label(sidebar, text="Smoothing Window (Stability)", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        window_row = ttk.Frame(sidebar, style="Card.TFrame")
        window_row.pack(fill="x", pady=5)
        
        self.step_window_var = tk.StringVar()
        entry_win = ttk.Entry(window_row, textvariable=self.step_window_var, width=15, font=("Segoe UI", 12))
        entry_win.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_win, self.step_window_var, "Set Window")
        ttk.Label(window_row, text="Steps", style="Sub.TLabel").pack(side="left", padx=(0, 5))
        ttk.Button(window_row, text="?", style="Help.TButton", width=2, command=self.show_window_help).pack(side="left", padx=5)

        # STRIDE CONFIG 
        ttk.Label(sidebar, text="Stride (Update Frequency)", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        stride_row = ttk.Frame(sidebar, style="Card.TFrame")
        stride_row.pack(fill="x", pady=5)
        self.stride_var = tk.StringVar()
        entry_stride = ttk.Entry(stride_row, textvariable=self.stride_var, width=15, font=("Segoe UI", 12))
        entry_stride.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_stride, self.stride_var, "Set Stride")
        ttk.Label(stride_row, text="Steps", style="Sub.TLabel").pack(side="left", padx=(0, 5))
        ttk.Button(stride_row, text="?", style="Help.TButton", width=2, command=self.show_stride_help).pack(side="left", padx=5)
        
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
        # Visualization Controls
        viz_controls = ttk.Frame(viz_root, style="TFrame")
        viz_controls.pack(fill="x", pady=(0, 5))
        
        self.show_2x_var = tk.BooleanVar(value=False)
        self.show_half_var = tk.BooleanVar(value=False)
        
        # Checkboxes
        ttk.Checkbutton(viz_controls, text="Show 2x BPM", variable=self.show_2x_var, 
                        command=self.update_plot_options).pack(side="right", padx=10)
        ttk.Checkbutton(viz_controls, text="Show 0.5x BPM", variable=self.show_half_var, 
                        command=self.update_plot_options).pack(side="right", padx=10)
        
        plot_card = ttk.Frame(viz_root, style="Card.TFrame", padding=10)
        plot_card.pack(fill="both", expand=True)
        
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.figure.patch.set_facecolor(self.P["card_bg"])
        # CHANGED: Single subplot (No bottom graph)
        self.ax1 = self.figure.add_subplot(111)
        self.ax2 = None # Explicitly None so Plotter knows
        self.figure.subplots_adjust(left=0.08, bottom=0.1, right=0.95, top=0.92)
        
        # Initialize Plotter Logic
        self.plotter = LivePlotter(self.ax1, self.P)
        # Initial style application (empty)
        self.plotter.update(pd.DataFrame({"seconds": [], "walking_bpm": [], "song_bpm": [], "step_event": []}))

        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.on_mode_change() # Init state
        self.poll_status()
        self.poll_session_dir()
        self.poll_status()
        self.poll_session_dir()
        self.poll_plot()
        self.poll_plot()
        if SERIAL_AVAILABLE:
            self.poll_ports() # Auto refresh ports
            
        self.refresh_session_list() # Init session list
        self.refresh_midi_list()    # Init MIDI list
        self.refresh_analysis_subjects() # Init Analysis list

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
            
    def get_midi_files(self):
        """Scans midi_files/ directory."""
        try:
            return [f.name for f in Path(__file__).resolve().parent.parent.joinpath("midi_files").glob("*.mid")]
        except: return []

    def refresh_midi_list(self):
        self.midi_combo['values'] = self.get_midi_files()
        if self.midi_combo['values']: self.midi_combo.current(0)
    
    def on_bpm_slider_change(self, val):
        """Handle slider movement with real-time update."""
        bpm = float(val)
        self.bpm_val_label.configure(text=f"{int(bpm)} BPM")
        
        # If in manual mode and running, update immediately
        if self.mode_var.get() == "manual":
            if self.session_thread: 
                self.session_thread.update_manual_bpm(bpm)
            # We don't log every single slide event to avoid spam, 
            # maybe just update label.
            
    def get_selected_port(self):
        val = self.port_var.get() if not SERIAL_AVAILABLE else self.port_combo.get()
        return val.split(" - ")[0] if " - " in val else val

    def on_mode_change(self):
        m = self.mode_var.get()
        if m == "manual":
            # Enable BPM controls
            for child in self.manual_bpm_frame.winfo_children():
                try: child.configure(state="normal")
                except: pass
            # Also the inner frames
            for child in self.manual_bpm_frame.winfo_children():
                if isinstance(child, ttk.Frame):
                    for gc in child.winfo_children():
                         try: gc.configure(state="normal")
                         except: pass
            
            if self.session_thread: self.session_thread.set_manual_mode(True)
            
            # Apply current BPM
            self.on_bpm_slider_change(self.manual_bpm_var.get())
            
        else:
            # Disable BPM controls
            for child in self.manual_bpm_frame.winfo_children():
                 try: child.configure(state="disabled")
                 except: pass
            for child in self.manual_bpm_frame.winfo_children():
                if isinstance(child, ttk.Frame):
                    for gc in child.winfo_children():
                         try: gc.configure(state="disabled")
                         except: pass
            
            if self.session_thread: self.session_thread.set_manual_mode(False)

    def start_session(self):
        """Action for the 'START SESSION' button."""
        if self.is_running: return
        
        # Clear any leftover live data/plot from previous session
        self.live_data_buffer = []
        while not self.data_queue.empty():
            self.data_queue.get_nowait()
        self.plotter.reset()
        self.canvas.draw_idle()
        
        # Resolve MIDI Path (Dropdown Name -> Full Path)
        m_name = self.midi_var.get()
        # Check if absolute path (from file picker) or relative (from dropdown)
        if Path(m_name).exists():
            p = Path(m_name)
        else:
            # Try finding it in midi_files
            p = Path(__file__).resolve().parent.parent / "midi_files" / m_name
            
        if not p.exists(): messagebox.showerror("Error", f"MIDI not found: {m_name}"); return
        
        port = self.get_selected_port()
        if not port or "No devices" in port:
            messagebox.showerror("Error", "Please select a valid Serial Port")
            return

        # Prepare parameters
        mm = self.mode_var.get() == "manual"
        # BPM is now from DoubleVar
        mb = self.manual_bpm_var.get() if mm else None
        
        # Session Name
        s_name = self.session_name_var.get().strip()
        if not s_name: s_name = None # Let logger generate timestamp

        try:
            raw_sw = self.step_window_var.get().strip()
            sw = int(raw_sw) if raw_sw and raw_sw.isdigit() else 6 
        except: sw = 6 

        try:
            raw_st = self.stride_var.get().strip()
            st = int(raw_st) if raw_st and raw_st.isdigit() else 1
        except: st = 1

        # Climbing/Cascading Alphas
        au = None
        try:
            val = self.smoothing_up_var.get().strip()
            if val: au = float(val)
        except: pass
        
        ad = None
        try:
            val = self.smoothing_down_var.get().strip()
            if val: ad = float(val)
        except: pass

        # Create and start the Subprocess Manager
        self.session_thread = SubprocessManager(str(p), port, mm, mb, sw, st, self.enqueue_status, self.enqueue_session_dir, self.enqueue_data, session_name=s_name, alpha_up=au, alpha_down=ad)
        
        # Reset RAM Buffer
        self.live_data_buffer = [] 
        # self.session_thread.start() # No longer needed as init starts it
        
        # Update UI state
        self.is_running = True
        self.btn_start.configure(state="disabled"); self.btn_stop.configure(state="normal")
        self._set_led(self.led_run, True, self.P["warning"]); self.log(f"Session running on {port}")

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
            
    def get_midi_files(self):
        """Scans midi_files/ directory."""
        try:
            base_dir = Path(__file__).resolve().parent.parent / "midi_files"
            if not base_dir.exists(): return []
            return [f.name for f in base_dir.glob("*.mid")]
        except: return []

    def refresh_midi_list(self):
        vals = self.get_midi_files()
        self.midi_combo['values'] = vals
        if vals and not self.midi_var.get():
             self.midi_combo.current(0)

    def get_existing_sessions(self):
        """
        Scans logs/ for custom session names (folders).
        Ignores default timestamped folders (start with 'session_').
        """
        try:
            log_dir = Path(__file__).resolve().parent.parent / "logs"
            if not log_dir.exists(): return []
            
            # Find folders that are NOT default sessions
            # Default sessions look like "session_2025-..."
            custom_names = []
            for d in log_dir.iterdir():
                if d.is_dir():
                    # Filter out default auto-generated folders ("session_2...") 
                    # to only show custom named sessions.
                    if not d.name.startswith("session_2"): 
                        custom_names.append(d.name)

            custom_names.sort()
            return custom_names
        except Exception:
            return []

    def refresh_session_list(self):
        vals = self.get_existing_sessions()
        
        # Determine strict type needed
        # If no files -> Entry (cleaner). If files -> Combobox (dropdown).
        target_type = ttk.Combobox if vals else ttk.Entry
        
        # Check current type
        current_type = type(self.session_input_widget)
        
        if current_type != target_type:
            # Swap Widget
            self.session_input_widget.destroy()
            if target_type == ttk.Combobox:
                self.session_input_widget = ttk.Combobox(self.session_row, textvariable=self.session_name_var)
                self.session_input_widget['values'] = vals
            else:
                self.session_input_widget = ttk.Entry(self.session_row, textvariable=self.session_name_var)
            
            # Repack (pack side=left puts it before the right-aligned button)
            self.session_input_widget.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
        elif vals and isinstance(self.session_input_widget, ttk.Combobox):
             self.session_input_widget['values'] = vals

        # Don't auto-select to preserve user input intent if they are typing


    def refresh_analysis_subjects(self):
        """Populate the first dropdown with Subject/Folder names."""
        try:
            log_dir = Path(__file__).resolve().parent / "logs"
            if not log_dir.exists(): 
                self.subject_combo['values'] = []
                return

            # Get just the directories (subjects)
            subjects = [d.name for d in log_dir.iterdir() if d.is_dir()]
            subjects.sort()
            
            self.subject_combo['values'] = subjects
            if subjects:
                self.subject_combo.current(0)
                self.on_subject_selected(None) # Trigger update of second list
        except Exception as e:
            print(f"Error loading subjects: {e}")

    def on_subject_selected(self, event):
        """When a subject is picked, populate the second dropdown with sessions."""
        subject = self.subject_var.get()
        if not subject: return
        
        try:
            log_dir = Path(__file__).resolve().parent / "logs" / subject
            if not log_dir.exists():
                self.session_combo['values'] = []
                return

            # Find session folders
            sessions = [d.name for d in log_dir.iterdir() if d.is_dir() and d.name.startswith("session_")]
            sessions.sort(reverse=True) # Newest first
            
            self.session_combo['values'] = sessions
            if sessions:
                self.session_combo.current(0)
            else:
                self.session_var.set("No sessions")
        except Exception as e:
            print(f"Error loading sessions: {e}")
             
    def view_session_plot(self):
        subject = self.subject_var.get()
        session_name = self.session_var.get()

        if not subject or not session_name or session_name == "No sessions":
            return
        
        # Construct path from both dropdowns
        base_dir = Path(__file__).resolve().parent / "logs" / subject / session_name
        plot_path = base_dir / "BPM_plot.png"
        
        if not plot_path.exists():
            # If PNG missing, try generate it on demand
            csv_path = base_dir / "session_data.csv"
            if csv_path.exists():
                try:
                    from utils.plotter import generate_post_session_plot
                    print(f"DEBUG: Generating plot for {base_dir}...")
                    generate_post_session_plot(base_dir)
                except Exception as e:
                    print(f"DEBUG: Plot generation failed: {e}")
                    import traceback
                    traceback.print_exc()
        
        if not plot_path.exists():
            messagebox.showinfo("No Plot", f"No plot found for {session_name}\n(Make sure the session finished correctly)")
            return
            
        # Create Popup Window
        top = tk.Toplevel(self.root)
        top.title(f"Analysis: {subject} / {session_name}")
        top.geometry("1100x850") # Fallback size
        top.configure(bg=self.P["bg"])
        
        # Maximize window (Windows only)
        try: top.state("zoomed")
        except: pass

        # Using Label with Dynamic Resizing (Requires Pillow)
        try:
            from PIL import Image, ImageTk
            
            # Load original image
            original_image = Image.open(plot_path)
            
            # Create a label to hold the image
            lbl = ttk.Label(top, background=self.P["bg"])
            lbl.pack(fill="both", expand=True)
            
            def resize_image(event):
                # Calculate aspect ratio to fit window
                new_width = event.width
                new_height = event.height
                
                if new_width < 10 or new_height < 10: return
                
                # Resize (LANCZOS for quality)
                resized = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(resized)
                
                lbl.configure(image=photo)
                lbl.image = photo # Keep reference
                
            # Bind resize event
            lbl.bind("<Configure>", resize_image)
            
        except ImportError:
            # Fallback to standard scrollbars if PIL not available (though it should be)
            print("DEBUG: PIL not found, falling back to scrollbars")
            container = ttk.Frame(top)
            container.pack(fill="both", expand=True)
            canvas = tk.Canvas(container, bg=self.P["bg"], highlightthickness=0)
            hbar = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
            vbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas, style="TFrame")
            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            vbar.pack(side="right", fill="y")
            hbar.pack(side="bottom", fill="x")
            
            try:
                img = tk.PhotoImage(file=str(plot_path))
                l = ttk.Label(scrollable_frame, image=img, background=self.P["bg"])
                l.image = img
                l.pack()
            except Exception as e:
                ttk.Label(scrollable_frame, text=f"Error: {e}").pack()




    def stop_session(self):
        """Action for the 'STOP SESSION' button."""
        if self.session_thread: self.session_thread.stop()
        self.is_running = False
        self.btn_start.configure(state="normal"); self.btn_stop.configure(state="disabled")
        self._set_led(self.led_run, False); self.log("Stopped")
        
        # VISUAL: Connect dots on stop
        try:
            if self.live_data_buffer:
                import pandas as pd
                df = pd.DataFrame(self.live_data_buffer)
                self.plotter.finalize_plot(df)
                self.canvas.draw()
        except Exception as e:
            print(f"Final plot update failed: {e}")

        # Generate Post-Session Plot
        if self.current_session_dir:
            try:
                self.log("Generating plot...")
                generate_post_session_plot(self.current_session_dir)
                self.log(f"Saved plot to {self.current_session_dir.name}")
            except Exception as e:
                self.log(f"Plot failed: {e}")



    def apply_smoothing_up(self):
        try:
            val = self.smoothing_up_var.get().strip()
            # If default/empty, use 0.02
            if not val or val == "Set Climbing": 
                v = 0.02
            else:
                v = float(val)
            if self.session_thread: self.session_thread.update_smoothing_alpha_up(v)
            self.log(f"Climbing set to {v}")
        except:
            self.log("Invalid Climbing value")

    def apply_smoothing_down(self):
        try:
            val = self.smoothing_down_var.get().strip()
            # If default/empty, use 0.05
            if not val or val == "Set Cascading":
                v = 0.05
            else:
                v = float(val)
            if self.session_thread: self.session_thread.update_smoothing_alpha_down(v)
            self.log(f"Cascading set to {v}")
        except:
            self.log("Invalid Cascading value")
            
    def apply_esp_config(self, type_key, var):
        """Sends new config to the running session thread."""
        if not self.session_thread or not self.is_running:
            self.log("Session not running - Setting saved for start")
            return

        try:
            val = var.get().strip()
            # Fallback for empty or placeholder text
            if not val or val.startswith("Set "):
                 v = 10 if type_key == "window" else 1
            else:
                 v = int(val)
                 
            self.session_thread.update_esp_config(type_key, v)
            self.log(f"{type_key.title()} set to {v}")
        except:
            self.log(f"Invalid {type_key} value")

    def show_attack_help(self):
        msg = ("Controls how fast the music SPEEDS UP when you accelerate.\n\n"
               "Low (0.02) = Gradual climbing.\n"
               "High (0.20) = Snappy response.\n"
               "Note: 'Sprint Boost' will override this if you run very fast.")
        messagebox.showinfo("Climbing Smoothing", msg)

    def show_decay_help(self):
        msg = ("Controls how fast the music SLOWS DOWN when you stop walking.\n\n"
               "Low (0.01) = Very slow, cinematic cascading.\n"
               "High (0.20) = Fast, responsive drop.\n\n"
                "Recommended: 0.02")
        messagebox.showinfo("Cascading Smoothing", msg)
        
    def show_window_help(self):
        msg = ("Controls how many steps are averaged to calculate your BPM.\n\n"
               "Low (1-3): Very responsive, but jumpy.\n"
               "High (10-20): Very stable, but reacts slowly.\n\n"
               "Recommended: 3-6")
        messagebox.showinfo("Step Averaging", msg)

    def show_stride_help(self):
        msg = ("Controls how often the music BPM is updated.\n\n"
               "1 = Update every step (Smoothest).\n"
               "2 = Update every 2 steps.\n"
               "4 = Update every 4 steps (Less CPU load).\n\n"
               "Recommended: 1")
        messagebox.showinfo("Update Stride", msg)

    def quit_app(self):
        """Cleanly exit the application."""
        self.is_app_active = False
        
        # Cancel all pending poll tasks to avoid "invalid command name" errors
        if self.job_status: self.root.after_cancel(self.job_status)
        if self.job_dir: self.root.after_cancel(self.job_dir)
        if self.job_plot: self.root.after_cancel(self.job_plot)
        if self.job_ports: self.root.after_cancel(self.job_ports)

        if self.session_thread: self.session_thread.stop()
        self.root.quit()
        self.root.destroy()

    # --- POLLING LOOPS ---
    # Tkinter isn't thread-safe, so we check Queues for messages from the background thread.
    
    def enqueue_status(self, m): self.status_queue.put(m)
    def enqueue_session_dir(self, p): self.session_dir_queue.put(p)
    def enqueue_data(self, d): self.data_queue.put(d)
    
    def poll_status(self):
        """Checks for new status messages every 200ms."""
        if not self.is_app_active: return
        while not self.status_queue.empty(): self.log(self.status_queue.get_nowait())
        self.job_status = self.root.after(200, self.poll_status)
        
    def poll_session_dir(self):
        """Checks if a new session folder was created."""
        if not self.is_app_active: return
        while not self.session_dir_queue.empty():
            self.current_session_dir = self.session_dir_queue.get_nowait()
            self.log(f"Logging: {self.current_session_dir.name}")
        self.job_dir = self.root.after(500, self.poll_session_dir)
        
    def poll_plot(self):
        """Updates the graph every 100ms."""
        if not self.is_app_active: return
        if self.current_session_dir: self.refresh_plot()
        self.job_plot = self.root.after(100, self.poll_plot)

    def poll_ports(self):
        """Checks for new serial ports every 2 seconds."""
        if not SERIAL_AVAILABLE: return
        try:
            current_selection = self.port_var.get()
            ports = serial.tools.list_ports.comports()
            new_values = [f"{p.device} - {p.description}" for p in ports]
            
            # Update only if changed to avoid UI flicker
            if list(self.port_combo['values']) != new_values:
                self.port_combo['values'] = new_values
                
                if not new_values:
                    self.port_combo.set("No devices found")
                elif current_selection not in new_values:
                    # Current selected device disappeared, or first run
                    if "No devices" in current_selection or current_selection == "":
                         self.port_combo.current(0)
                    else:
                        # Keep showing the old name (e.g. COM3) even if disconnected?
                        # Or switch to first available? Let's switch to first available.
                        self.port_combo.current(0)
                        
        except Exception: 
            pass
        self.job_ports = self.root.after(2000, self.poll_ports)

    def refresh_plot(self):
        """
        Reads from RAM Buffer (Fast!) instead of Disk CSV.
        """
        # 1. Drain Queue into RAM Buffer
        while not self.data_queue.empty():
            self.live_data_buffer.append(self.data_queue.get_nowait())
        
        # SAFETY: trim to recent window to keep Tk/Matplotlib responsive
        if len(self.live_data_buffer) > self.max_live_points:
            self.live_data_buffer = self.live_data_buffer[-self.max_live_points:]
            
        if not self.live_data_buffer: return

        # 2. Convert to DataFrame
        try:
            # We construct DataFrame from list of dicts (Very fast)
            # Keys: t, s, w, e
            df = pd.DataFrame(self.live_data_buffer)

            # Keep only the most recent window before plotting to reduce draw cost
            if len(df) > self.max_live_points:
                df = df.tail(self.max_live_points).reset_index(drop=True)
            
            # Rename match plotter expectations
            # Packet keys: t=time_str, s=song, w=walking, e=event
            df.rename(columns={"t": "time", "s": "song_bpm", "w": "walking_bpm", "e": "step_event"}, inplace=True)
            
            if "time" in df.columns:
                 df["seconds"] = df["time"].apply(_elapsed_to_seconds)
            else:
                 df["seconds"] = df.index
            
            # Ensure boolean
            if "step_event" in df.columns:
                 # It comes as boolean from JSON, but just in case
                 df["step_event"] = df["step_event"].astype(bool)

        except Exception: 
            return
        
        # Delegate to Plotter
        self.plotter.update(df)
        self.figure.tight_layout(); self.canvas.draw_idle()

    def update_plot_options(self):
        """Callback for the 2x/0.5x BPM checkboxes."""
        self.plotter.set_show_multipliers(self.show_2x_var.get(), self.show_half_var.get())
        # Force immediate refresh of current view if data exists
        if self.live_data_buffer:
            self.refresh_plot()

    @staticmethod
    def _parse_bpm(v):
        try: return float(v) if float(v) >= 0 else None
        except: return None

    def _bind_placeholder(self, entry, text_var, placeholder):
        """Adds placeholder text to an entry."""
        def on_focus_in(event):
            if text_var.get() == placeholder:
                text_var.set("")
                entry.configure(foreground=self.P["text_input"])
        def on_focus_out(event):
            if not text_var.get():
                text_var.set(placeholder)
                entry.configure(foreground="#94a3b8")
        if not text_var.get() or text_var.get() == placeholder:
            text_var.set(placeholder)
            entry.configure(foreground="#94a3b8")
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

def main():
    root = tk.Tk()
    try: from ctypes import windll; windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    GuiApp(root)
    root.mainloop()

if __name__ == "__main__": main()
