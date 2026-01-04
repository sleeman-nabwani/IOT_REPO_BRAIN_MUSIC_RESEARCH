import threading
from queue import SimpleQueue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time

import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# --- Mock imports for context ---
try:
    from utils.plotter import _elapsed_to_seconds, LivePlotter, generate_post_session_plot
    from utils.process_manager import SubprocessManager
    from utils.comms import send_calibration_command
except ImportError:
    send_calibration_command = None
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


# --- HELPER CLASS FOR COLLAPSIBLE SECTIONS ---
class CollapsiblePane(ttk.Frame):
    def __init__(self, parent, title="", expanded=False, style_prefix=""):
        # Match parent style (Card.TFrame) to avoid "black line" effect from default TFrame bg
        super().__init__(parent, style="Card.TFrame")
        self.parent = parent
        self.expanded = expanded
        self.title = title
        
        # Toggle Button
        self.toggle_btn = ttk.Button(self, text=self._get_title(), command=self.toggle, style="Compact.TButton", width=100) # Wide button
        self.toggle_btn.pack(fill="x", anchor="n")
        
        # Content Frame (Hidden by default)
        self.content_frame = ttk.Frame(self, style="Card.TFrame")
        
        if expanded:
            self.content_frame.pack(fill="x", expand=True)

    def _get_title(self):
        return f"▼ {self.title}" if self.expanded else f"▶ {self.title}"

    def toggle(self):
        self.expanded = not self.expanded
        self.toggle_btn.configure(text=self._get_title())
        if self.expanded:
            self.content_frame.pack(fill="x", expand=True) # Removed pady=5 to remove gap
        else:
            self.content_frame.pack_forget()


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
        # Success (green) button for calibration
        style.configure("Success.TButton", font=("Segoe UI", 10, "bold"), background=self.P["success"], foreground="white", borderwidth=0, padding=(15, 10))
        style.map("Success.TButton", background=[("active", "#16a34a")])
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

        # PanedWindow and Separator styling for dark theme
        style.configure("TPanedwindow", background=self.P["bg"])
        style.configure("TSeparator", background=self.P["border"])
        # Sub label variant for card backgrounds
        style.configure("CardSub.TLabel", font=("Segoe UI", 11), foreground=self.P["text_sub"], background=self.P["card_bg"])
        # Treeview dark styling
        style.configure("Treeview", background=self.P["card_bg"], foreground=self.P["text_main"],
                        fieldbackground=self.P["card_bg"], borderwidth=0)
        style.map("Treeview", background=[("selected", self.P["accent"])], foreground=[("selected", "white")])

        base_dir = Path(__file__).resolve().parent.parent
        default_midi = base_dir / "midi_files" / "Technion_March1.mid"
        
        self.session_thread = None
        self.status_queue = SimpleQueue()
        self.session_dir_queue = SimpleQueue()
        self.data_queue = SimpleQueue()
        self.current_session_dir = None
        self.live_data_buffer = []
        # Limit how many points we render per frame (buffer keeps full history)
        self.max_live_points = 2500
        # Sliding window controls
        self.view_window_sec = 240  # visible time window for live plot
        self.buffer_cap = 30000     # absolute cap to avoid unbounded growth
        # Live plot uses subplots_adjust; avoid tight_layout in the hot path for FPS stability.
        self._did_tight_layout = True
        self.is_running = False
        self.is_calibrating = False
        self.is_app_active = True
        # Poll jobs
        self.job_status = None
        self.job_dir = None
        self.job_plot = None
        self.job_ports = None
        
        self.port_scan_thread = None


        self.port_scan_thread = None

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
        ttk.Radiobutton(sidebar, text="🚀 Hybrid (Cruise Control)", value="hybrid", variable=self.mode_var, command=self.on_mode_change).pack(anchor="w", pady=5)
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


        # --- ADVANCED SETTINGS (COLLAPSIBLE) ---
        self.advanced_pane = CollapsiblePane(sidebar, title="Advanced Settings", expanded=False)
        self.advanced_pane.pack(fill="x", pady=(15, 0))
        
        # Re-parent controls to [self.advanced_pane.content_frame] instead of [sidebar]
        adv_parent = self.advanced_pane.content_frame
        
        # SMOOTHING CONTROL (Climbing & Cascading)
        ttk.Label(adv_parent, text="CLIMBING (SPEEDING UP)", style="CardHeader.TLabel").pack(anchor="w", pady=(5, 0))
        
        attack_row = ttk.Frame(adv_parent, style="Card.TFrame")
        attack_row.pack(fill="x", pady=5)
        
        self.smoothing_up_var = tk.StringVar() 
        entry_up = ttk.Entry(attack_row, textvariable=self.smoothing_up_var, width=15, font=("Segoe UI", 12))
        entry_up.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_up, self.smoothing_up_var, "Default (engine)")
        
        ttk.Button(attack_row, text="?", style="Help.TButton", width=2, command=self.show_attack_help).pack(side="left", padx=5)

        # Cascading
        ttk.Label(adv_parent, text="CASCADING (SLOWING DOWN)", style="CardHeader.TLabel").pack(anchor="w", pady=(15, 0))
        
        decay_row = ttk.Frame(adv_parent, style="Card.TFrame")
        decay_row.pack(fill="x", pady=5)
        
        self.smoothing_down_var = tk.StringVar()
        entry_down = ttk.Entry(decay_row, textvariable=self.smoothing_down_var, width=15, font=("Segoe UI", 12))
        entry_down.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_down, self.smoothing_down_var, "Default (engine)")

        ttk.Button(decay_row, text="?", style="Help.TButton", width=2, command=self.show_decay_help).pack(side="left", padx=5)

        # STEP AVERAGING WINDOW (ESP32 Config)
        ttk.Label(adv_parent, text="Smoothing Window (Stability)", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        window_row = ttk.Frame(adv_parent, style="Card.TFrame")
        window_row.pack(fill="x", pady=5)
        
        self.step_window_var = tk.StringVar()
        entry_win = ttk.Entry(window_row, textvariable=self.step_window_var, width=15, font=("Segoe UI", 12))
        entry_win.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_win, self.step_window_var, "Default (engine)")
        ttk.Label(window_row, text="Steps", style="Sub.TLabel").pack(side="left", padx=(0, 5))
        ttk.Button(window_row, text="?", style="Help.TButton", width=2, command=self.show_window_help).pack(side="left", padx=5)

        # STRIDE CONFIG 
        ttk.Label(adv_parent, text="Stride (Update Frequency)", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        stride_row = ttk.Frame(adv_parent, style="Card.TFrame")
        stride_row.pack(fill="x", pady=5)
        self.stride_var = tk.StringVar()
        entry_stride = ttk.Entry(stride_row, textvariable=self.stride_var, width=15, font=("Segoe UI", 12))
        entry_stride.pack(side="left", padx=(0, 5))
        self._bind_placeholder(entry_stride, self.stride_var, "Set Stride")
        ttk.Label(stride_row, text="Steps", style="Sub.TLabel").pack(side="left", padx=(0, 5))
        ttk.Button(stride_row, text="?", style="Help.TButton", width=2, command=self.show_stride_help).pack(side="left", padx=5)

        # PREDICTION MODEL SELECTOR
        ttk.Label(adv_parent, text="Prediction Model", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        model_row = ttk.Frame(adv_parent, style="Card.TFrame")
        model_row.pack(fill="x", pady=5)
        self.model_var = tk.StringVar(value="Base Model")
        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_var, state="readonly", width=25)
        self.model_combo.pack(side="left", padx=(0, 5))
        ttk.Button(model_row, text="↻", style="Compact.TButton", width=3, command=self._refresh_model_list).pack(side="left")
        self._refresh_model_list()  # Populate on init
        
        # Weight Calibration (Advanced)
        ttk.Label(adv_parent, text="Weight Calibration", style="CardHeader.TLabel").pack(anchor="w", pady=(10, 0))
        cali_frame = ttk.Frame(adv_parent, style="Card.TFrame")
        cali_frame.pack(fill="x", pady=5)
        ttk.Label(cali_frame, text="Margin", style="Sub.TLabel").pack(side="left", padx=(0, 5))
        self.cal_margin_var = tk.StringVar(value="200")
        ttk.Entry(cali_frame, textvariable=self.cal_margin_var, width=10).pack(side="left", padx=(0, 5))
        
        # --- BOTTOM CONTROLS ---
        ttk.Frame(sidebar, style="Card.TFrame").pack(fill="both", expand=True) # Spacer pushes everything down

        section("Session Control")
        self.btn_start = ttk.Button(sidebar, text="▶ START SESSION", command=self.start_session, style="Primary.TButton")
        self.btn_start.pack(fill="x", pady=(0, 10))
        
        self.btn_stop = ttk.Button(sidebar, text="⏹ STOP SESSION", command=self.stop_session, style="Danger.TButton", state="disabled")
        self.btn_stop.pack(fill="x", pady=(0, 10))
        
        self.btn_calibrate = ttk.Button(sidebar, text="✅ CALIBRATE WEIGHT", command=self.on_calibrate_weight, style="Success.TButton")
        self.btn_calibrate.pack(fill="x", pady=(0, 10))

        self.btn_quit = ttk.Button(sidebar, text="❌ QUIT APP", command=self.quit_app, style="Secondary.TButton")
        self.btn_quit.pack(fill="x")

        # ====================== TABBED MAIN AREA ======================
        # Notebook for switching between Session (live plot) and Training tabs
        self.main_notebook = ttk.Notebook(main_body)
        self.main_notebook.grid(row=0, column=1, sticky="nsew")

        # Configure Notebook style
        style.configure("TNotebook", background=self.P["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(15, 8),
                        background=self.P["card_bg"], foreground=self.P["text_sub"])
        style.map("TNotebook.Tab",
                  background=[("selected", self.P["accent"])],
                  foreground=[("selected", "white")])

        # -------------------- TAB 1: SESSION (Live Plot) --------------------
        tab_session = ttk.Frame(self.main_notebook, style="TFrame")
        self.main_notebook.add(tab_session, text="  ▶ Session  ")

        viz_controls = ttk.Frame(tab_session, style="TFrame")
        viz_controls.pack(fill="x", pady=(0, 5))
        
        self.show_2x_var = tk.BooleanVar(value=False)
        self.show_half_var = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(viz_controls, text="Show 2x BPM", variable=self.show_2x_var, 
                        command=self.update_plot_options).pack(side="right", padx=10)
        ttk.Checkbutton(viz_controls, text="Show 0.5x BPM", variable=self.show_half_var, 
                        command=self.update_plot_options).pack(side="right", padx=10)
        
        plot_card = ttk.Frame(tab_session, style="Card.TFrame", padding=10)
        plot_card.pack(fill="both", expand=True)
        
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.figure.patch.set_facecolor(self.P["card_bg"])
        self.ax1 = self.figure.add_subplot(111)
        self.ax2 = None
        self.figure.subplots_adjust(left=0.08, bottom=0.1, right=0.95, top=0.92)
        
        self.plotter = LivePlotter(self.ax1, self.P)
        self.plotter.view_window_sec = self.view_window_sec
        self.plotter.update(pd.DataFrame({"seconds": [], "walking_bpm": [], "song_bpm": [], "step_event": []}))

        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # -------------------- TAB 2: MODEL TRAINING --------------------
        tab_training = ttk.Frame(self.main_notebook, style="TFrame")
        self.main_notebook.add(tab_training, text="  🧠 Training  ")

        self._build_training_tab(tab_training)

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

    def _refresh_model_list(self):
        """Scan for available prediction models (base + user heads)."""
        models_dir = Path(__file__).resolve().parent.parent / "research" / "LightGBM" / "results" / "models"
        model_options = []
        self._model_paths = {}  # Map display name -> actual path
        
        # Base model
        base_model = models_dir / "lgbm_model.joblib"
        if base_model.exists():
            model_options.append("Base Model")
            self._model_paths["Base Model"] = str(base_model)
        
        # User head models
        for head in sorted(models_dir.glob("lgbm_user_head_*.joblib")):
            suffix = head.stem.replace("lgbm_user_head_", "")
            display_name = f"User Head: {suffix}"
            model_options.append(display_name)
            self._model_paths[display_name] = str(head)
        
        if not model_options:
            model_options = ["No models found"]
            self._model_paths["No models found"] = None
        
        self.model_combo['values'] = model_options
        if model_options and self.model_var.get() not in model_options:
            self.model_combo.current(0)

    def get_selected_model_path(self):
        """Return the file path of the selected prediction model, or None."""
        selected = self.model_var.get()
        return self._model_paths.get(selected)
    
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
        if self.is_training:
            self.log("Cannot start session while training is in progress.")
            return

        # Clear any leftover live data/plot from previous session
        self.live_data_buffer = []
        while not self.data_queue.empty():
            self.data_queue.get_nowait()
        self.plotter.reset()
        # Pre-warm renderer so the first incoming packets do not pay the initial draw cost.
        try:
            self.canvas.draw()
        except Exception:
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
            sw = int(raw_sw) if raw_sw and raw_sw.isdigit() else None  # None -> use engine default
        except:
            sw = None

        try:
            raw_st = self.stride_var.get().strip()
            st = int(raw_st) if raw_st and raw_st.isdigit() else None  # None -> use engine default
        except:
            st = None

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

        # Get selected prediction model path
        model_path = self.get_selected_model_path()
        
        # Create and start the Subprocess Manager
        self.session_thread = SubprocessManager(
            str(p),
            port,
            mm,
            mb,
            sw,
            st,
            self.enqueue_status,
            self.enqueue_session_dir,
            self.enqueue_data,
            session_name=s_name,
            alpha_up=au,
            alpha_down=ad,
            hybrid_mode=(self.mode_var.get() == "hybrid"),
            model_path=model_path,
        )
        
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
        
        # Always use a Combobox (Writable) so user can Type NEW or Select EXISTING
        # We assume self.session_input_widget is already a Combobox (created in __init__)
        
        # Ensure it has not been swapped to an Entry by legacy code
        if not isinstance(self.session_input_widget, ttk.Combobox):
            # If for some reason it's an Entry, swap it back to Combobox permanently
            self.session_input_widget.destroy()
            self.session_input_widget = ttk.Combobox(self.session_row, textvariable=self.session_name_var)
            self.session_input_widget.pack(side="left", fill="x", expand=True, padx=(0, 5))
            
        self.session_input_widget['values'] = vals



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
                
                # Preprocess DF (match logic in refresh_plot)
                df.rename(columns={"t": "time", "s": "song_bpm", "w": "walking_bpm", "e": "step_event"}, inplace=True)
                if "time" in df.columns:
                     df["seconds"] = df["time"].apply(_elapsed_to_seconds)
                else:
                     df["seconds"] = df.index
                     
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

        # Reset live buffers and plot for next session
        # self.live_data_buffer = [] # Retain buffer so user can see last session
        # if self.plotter:
        #    self.plotter.reset()
        #    self._did_tight_layout = False
        try:
            self.canvas.draw_idle()
        except Exception:
            pass



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

    def on_calibrate_weight(self):
        """Run calibration without requiring a session; blocks start until done."""
        if self.is_calibrating:
            self.log("Calibration already in progress.")
            return
        if send_calibration_command is None:
            self.log("Calibration helper unavailable.")
            return

        # Derive port (strip description if needed)
        port_val = self.port_var.get().strip()
        if not port_val:
            self.log("Select a serial port first.")
            return
        # If combobox value is like "COM3 - desc", take first token
        port = port_val.split()[0]

        try:
            margin = int(self.cal_margin_var.get())
        except ValueError:
            margin = 200
            self.log("Invalid margin; using 200.")

        # UI lockout during calibration
        self.is_calibrating = True
        self._cal_spinner_idx = 0
        self.btn_calibrate.configure(state="disabled")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="disabled")
        self._animate_calibration_spinner()

        def _worker():
            ok = False
            try:
                import serial
                with serial.Serial(port, 115200, timeout=1.0) as ser:
                    class _Logger:
                        def log(self, msg): self_outer.log(msg)
                    ok = send_calibration_command(ser, _Logger(), margin=margin, retries=3)
            except Exception as e:
                self.log(f"Calibration failed: {e}")
            finally:
                self.root.after(0, lambda ok=ok: self._finish_calibration(ok))

        self_outer = self
        threading.Thread(target=_worker, daemon=True).start()

    def _animate_calibration_spinner(self):
        """Animate spinner in calibration button while calibrating."""
        if not self.is_calibrating:
            return
        frames = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
        self.btn_calibrate.configure(text=f"Calibrating {frames[self._cal_spinner_idx % len(frames)]}")
        self._cal_spinner_idx += 1
        self.root.after(100, self._animate_calibration_spinner)

    def _finish_calibration(self, success: bool):
        """Reset UI after calibration with brief result flash."""
        self.is_calibrating = False
        # Show result briefly
        if success:
            self.btn_calibrate.configure(text="✓ Done!", state="disabled")
            self.log("Calibration completed.")
        else:
            self.btn_calibrate.configure(text="✗ Failed", state="disabled")
        # Restore button after delay
        self.root.after(1500, self._restore_calibration_button)

    def _restore_calibration_button(self):
        """Restore calibration button to normal state."""
        self.btn_calibrate.configure(state="normal", text="✅ CALIBRATE WEIGHT")
        # Re-enable start; stop remains as-is depending on running state
        if not self.is_running:
            self.btn_start.configure(state="normal")
        else:
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")

    # ====================== TRAINING TAB ======================
    def _build_training_tab(self, parent):
        """Build the Model Training tab UI."""
        self.is_training = False
        self.training_process = None

        # Use PanedWindow for resizable two-column layout
        paned = ttk.PanedWindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- LEFT: Session Selection ----
        left_card = ttk.Frame(paned, style="Card.TFrame", padding=15)
        paned.add(left_card, weight=1)

        ttk.Label(left_card, text="Select Sessions for Training", style="CardHeader.TLabel").pack(anchor="w")
        ttk.Label(left_card, text="Check users/sessions to include in training data",
                  style="CardSub.TLabel").pack(anchor="w", pady=(0, 10))

        # Treeview for session selection
        tree_frame = ttk.Frame(left_card, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        self.session_tree = ttk.Treeview(tree_frame, columns=("sessions",), show="tree",
                                          selectmode="extended", yscrollcommand=tree_scroll.set)
        tree_scroll.configure(command=self.session_tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.session_tree.pack(side="left", fill="both", expand=True)

        self.session_tree.column("#0", width=300, stretch=True)
        self.session_tree.heading("#0", text="User / Session")

        # Buttons under tree
        tree_btn_frame = ttk.Frame(left_card, style="Card.TFrame")
        tree_btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(tree_btn_frame, text="↻ Refresh", command=self._refresh_training_sessions,
                   style="Compact.TButton").pack(side="left", padx=(0, 5))
        ttk.Button(tree_btn_frame, text="Select All", command=self._select_all_sessions,
                   style="Compact.TButton").pack(side="left", padx=(0, 5))
        ttk.Button(tree_btn_frame, text="Clear", command=self._clear_session_selection,
                   style="Compact.TButton").pack(side="left")

        # ---- RIGHT: Training Options & Controls ----
        right_card = ttk.Frame(paned, style="Card.TFrame", padding=15)
        paned.add(right_card, weight=1)

        ttk.Label(right_card, text="Training Options", style="CardHeader.TLabel").pack(anchor="w")

        # Algorithm selection
        algo_frame = ttk.Frame(right_card, style="Card.TFrame")
        algo_frame.pack(fill="x", pady=(10, 5))
        ttk.Label(algo_frame, text="Algorithm:", style="CardLabel.TLabel").pack(side="left")
        self.algo_var = tk.StringVar(value="LightGBM")
        algo_combo = ttk.Combobox(algo_frame, textvariable=self.algo_var, state="readonly", width=15)
        algo_combo['values'] = ["LightGBM"]  # Expandable later
        algo_combo.pack(side="left", padx=(10, 0))

        # Training type selection
        type_frame = ttk.Frame(right_card, style="Card.TFrame")
        type_frame.pack(fill="x", pady=5)
        ttk.Label(type_frame, text="Training Type:", style="CardLabel.TLabel").pack(side="left")
        self.train_type_var = tk.StringVar(value="base")
        ttk.Radiobutton(type_frame, text="Base Model", variable=self.train_type_var, value="base").pack(side="left", padx=(10, 5))
        ttk.Radiobutton(type_frame, text="User Head", variable=self.train_type_var, value="user_head").pack(side="left")

        # User head options (shown when user_head selected)
        self.user_head_frame = ttk.Frame(right_card, style="Card.TFrame")
        self.user_head_frame.pack(fill="x", pady=5)
        ttk.Label(self.user_head_frame, text="User Name:", style="CardLabel.TLabel").pack(side="left")
        self.user_head_name_var = tk.StringVar(value="")
        ttk.Entry(self.user_head_frame, textvariable=self.user_head_name_var, width=20).pack(side="left", padx=(10, 0))
        ttk.Label(self.user_head_frame, text="(for saving head artifact)", style="CardSub.TLabel").pack(side="left", padx=(5, 0))

        # Optuna optimization checkbox (only for base model)
        optuna_frame = ttk.Frame(right_card, style="Card.TFrame")
        optuna_frame.pack(fill="x", pady=5)
        self.optuna_var = tk.BooleanVar(value=False)
        self.optuna_check = ttk.Checkbutton(optuna_frame, text="Optuna Hyperparameter Optimization",
                                             variable=self.optuna_var, command=self._on_optuna_change)
        self.optuna_check.pack(side="left")
        
        # Optuna trials setting
        self.optuna_trials_frame = ttk.Frame(right_card, style="Card.TFrame")
        ttk.Label(self.optuna_trials_frame, text="Trials:", style="CardLabel.TLabel").pack(side="left")
        self.optuna_trials_var = tk.StringVar(value="30")
        ttk.Entry(self.optuna_trials_frame, textvariable=self.optuna_trials_var, width=6).pack(side="left", padx=(5, 0))
        ttk.Label(self.optuna_trials_frame, text="(more = better but slower)", style="CardSub.TLabel").pack(side="left", padx=(5, 0))

        # Bind radio button change (must be after optuna widgets are created)
        self.train_type_var.trace_add("write", lambda *_: self._on_train_type_change())
        self._on_train_type_change()  # Initial state

        # Separator
        ttk.Separator(right_card, orient="horizontal").pack(fill="x", pady=15)

        # Progress section
        ttk.Label(right_card, text="Training Progress", style="CardHeader.TLabel").pack(anchor="w")

        self.train_progress = ttk.Progressbar(right_card, mode="indeterminate", length=300)
        self.train_progress.pack(fill="x", pady=(10, 5))

        self.train_status_var = tk.StringVar(value="Ready to train")
        ttk.Label(right_card, textvariable=self.train_status_var, style="CardSub.TLabel").pack(anchor="w")

        # Training log (small text area)
        log_frame = ttk.Frame(right_card, style="Card.TFrame")
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.train_log = tk.Text(log_frame, height=8, wrap="word", font=("Consolas", 9),
                                  bg=self.P["bg"], fg=self.P["text_main"], insertbackground=self.P["text_main"],
                                  relief="flat", borderwidth=2)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.train_log.yview)
        self.train_log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.train_log.pack(side="left", fill="both", expand=True)
        self.train_log.configure(state="disabled")

        # Buttons row
        btn_row = ttk.Frame(right_card, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(15, 0))

        self.btn_train = ttk.Button(btn_row, text="🚀 START TRAINING", command=self._start_training,
                                     style="Primary.TButton")
        self.btn_train.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_view_results = ttk.Button(btn_row, text="📊 VIEW RESULTS", command=self._view_training_results,
                                            style="Secondary.TButton")
        self.btn_view_results.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Populate sessions on init
        self.root.after(100, self._refresh_training_sessions)

    def _on_train_type_change(self):
        """Show/hide user head options based on selection."""
        # Guard: optuna widgets may not exist yet during init
        has_optuna = hasattr(self, "optuna_check")
        
        if self.train_type_var.get() == "user_head":
            self.user_head_frame.pack(fill="x", pady=5)
            if has_optuna:
                self.optuna_check.configure(state="disabled")
                self.optuna_var.set(False)
                self.optuna_trials_frame.pack_forget()
        else:
            self.user_head_frame.pack_forget()
            if has_optuna:
                self.optuna_check.configure(state="normal")

    def _on_optuna_change(self):
        """Show/hide Optuna trials setting based on checkbox."""
        if self.optuna_var.get():
            self.optuna_trials_frame.pack(fill="x", pady=5)
        else:
            self.optuna_trials_frame.pack_forget()

    def _refresh_training_sessions(self):
        """Scan logs directory and populate session tree."""
        self.session_tree.delete(*self.session_tree.get_children())
        logs_dir = Path(__file__).resolve().parent / "logs"
        if not logs_dir.exists():
            return

        for user_dir in sorted(logs_dir.iterdir()):
            if not user_dir.is_dir():
                continue
            user_node = self.session_tree.insert("", "end", text=f"📁 {user_dir.name}", open=False, tags=("user",))
            sessions = sorted(user_dir.glob("session_*/session_data.csv"))
            for sess in sessions:
                sess_name = sess.parent.name
                self.session_tree.insert(user_node, "end", text=f"  📄 {sess_name}",
                                          values=(str(sess),), tags=("session",))

    def _select_all_sessions(self):
        """Select all items in session tree."""
        def select_recursive(item):
            self.session_tree.selection_add(item)
            for child in self.session_tree.get_children(item):
                select_recursive(child)
        for item in self.session_tree.get_children():
            select_recursive(item)

    def _clear_session_selection(self):
        """Clear all selections in session tree."""
        self.session_tree.selection_remove(*self.session_tree.selection())

    def _get_selected_session_paths(self):
        """Get list of selected session CSV paths."""
        paths = []
        for item in self.session_tree.selection():
            tags = self.session_tree.item(item, "tags")
            if "session" in tags:
                vals = self.session_tree.item(item, "values")
                if vals:
                    paths.append(vals[0])
            elif "user" in tags:
                # If user folder selected, include all its sessions
                for child in self.session_tree.get_children(item):
                    vals = self.session_tree.item(child, "values")
                    if vals:
                        paths.append(vals[0])
        return list(set(paths))  # Dedupe

    def _log_training(self, msg):
        """Append message to training log."""
        self.train_log.configure(state="normal")
        self.train_log.insert("end", msg + "\n")
        self.train_log.see("end")
        self.train_log.configure(state="disabled")

    def _start_training(self):
        """Start model training as background subprocess."""
        print("[DEBUG] _start_training called")
        if self.is_training:
            self.log("Training already in progress.")
            return
        if self.is_running:
            self.log("Cannot train while a session is running.")
            return

        selected = self._get_selected_session_paths()
        print(f"[DEBUG] Selected {len(selected)} sessions")
        if not selected:
            self.log("Select at least one session to train on.")
            return

        train_type = self.train_type_var.get()
        user_head_name = self.user_head_name_var.get().strip()
        print(f"[DEBUG] train_type={train_type}, user_head_name='{user_head_name}'")
        use_optuna = self.optuna_var.get() and train_type == "base"
        try:
            optuna_trials = int(self.optuna_trials_var.get())
        except ValueError:
            optuna_trials = 30

        if train_type == "user_head" and not user_head_name:
            self.log("Enter a user name for the head artifact.")
            print("[DEBUG] Missing user name for user_head training")
            return
        
        print("[DEBUG] Starting training worker thread...")

        # Lock UI
        self.is_training = True
        self.btn_train.configure(state="disabled", text="Training...")
        self.btn_start.configure(state="disabled")
        self.train_progress.start(10)
        self.train_status_var.set("Training in progress...")
        self.train_log.configure(state="normal")
        self.train_log.delete("1.0", "end")
        self.train_log.configure(state="disabled")

        mode = f"{train_type} + Optuna ({optuna_trials} trials)" if use_optuna else train_type
        self._log_training(f"Starting {mode} training with {len(selected)} session(s)...")

        # Run training in background thread
        def _worker():
            import subprocess
            import sys
            try:
                # Write sessions to a temp file to avoid command-line length limits on Windows
                import tempfile
                sessions_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                for s in selected:
                    sessions_file.write(s + '\n')
                sessions_file.close()
                
                if train_type == "base":
                    # Run train_lgbm.py with selected sessions
                    script = Path(__file__).resolve().parent.parent / "research" / "LightGBM" / "train_lgbm.py"
                    cmd = [sys.executable, str(script), "--sessions-file", sessions_file.name]
                    # Add Optuna optimization if enabled
                    if use_optuna:
                        cmd.append("--optimize")
                        cmd.extend(["--trials", str(optuna_trials)])
                else:
                    # Run train_user_head.py with selected sessions
                    script = Path(__file__).resolve().parent.parent / "research" / "LightGBM" / "train_user_head.py"
                    cmd = [sys.executable, str(script), "--sessions-file", sessions_file.name, "--suffix", user_head_name.replace(" ", "_")]

                self.root.after(0, lambda: self._log_training(f"Running: {' '.join(cmd)}"))

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(Path(__file__).resolve().parent.parent)
                )
                self.training_process = proc

                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        self.root.after(0, lambda l=line: self._log_training(l))

                proc.wait()
                success = proc.returncode == 0
                self.root.after(0, lambda: self._finish_training(success))

            except Exception as e:
                self.root.after(0, lambda: self._log_training(f"Error: {e}"))
                self.root.after(0, lambda: self._finish_training(False))
            finally:
                # Cleanup temp sessions file
                try:
                    import os
                    if 'sessions_file' in dir() and sessions_file and os.path.exists(sessions_file.name):
                        os.unlink(sessions_file.name)
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_training(self, success: bool):
        """Reset UI after training completes."""
        self.is_training = False
        self.training_process = None
        self.train_progress.stop()

        if success:
            self.train_status_var.set("✓ Training completed successfully!")
            self._log_training("Training finished successfully.")
            self.btn_train.configure(text="✓ Done!")
        else:
            self.train_status_var.set("✗ Training failed")
            self._log_training("Training failed. Check log above.")
            self.btn_train.configure(text="✗ Failed")

        # Restore button after delay
        self.root.after(2000, self._restore_train_button)

    def _restore_train_button(self):
        """Restore train button to normal state."""
        self.btn_train.configure(state="normal", text="🚀 START TRAINING")
        if not self.is_running:
            self.btn_start.configure(state="normal")

    def _view_training_results(self):
        """Open a window displaying training result plots."""
        results_dir = Path(__file__).resolve().parent.parent / "research" / "LightGBM" / "results" / "plots"
        
        if not results_dir.exists():
            messagebox.showinfo("No Results", "No training results found. Run training first.")
            return
        
        # Find available plots
        plots = list(results_dir.glob("*.png"))
        if not plots:
            messagebox.showinfo("No Results", "No plot images found in results directory.")
            return
        
        # Create results window
        results_win = tk.Toplevel(self.root)
        results_win.title("Training Results")
        results_win.geometry("900x700")
        results_win.configure(bg=self.P["bg"])
        
        # Header
        header = ttk.Frame(results_win, style="TFrame")
        header.pack(fill="x", padx=20, pady=(20, 10))
        ttk.Label(header, text="📊 Model Training Results", style="H1.TLabel").pack(anchor="w")
        ttk.Label(header, text=f"Found {len(plots)} result plot(s)", style="Sub.TLabel").pack(anchor="w")
        
        # Plot selector
        selector_frame = ttk.Frame(results_win, style="TFrame")
        selector_frame.pack(fill="x", padx=20, pady=(0, 10))
        ttk.Label(selector_frame, text="Select Plot:", style="Sub.TLabel").pack(side="left")
        
        plot_names = [p.stem for p in sorted(plots)]
        plot_var = tk.StringVar(value=plot_names[0] if plot_names else "")
        plot_combo = ttk.Combobox(selector_frame, textvariable=plot_var, values=plot_names, state="readonly", width=40)
        plot_combo.pack(side="left", padx=(10, 0))
        
        # Image display area
        img_frame = ttk.Frame(results_win, style="Card.TFrame", padding=10)
        img_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        img_label = ttk.Label(img_frame, text="Select a plot to view", style="CardLabel.TLabel")
        img_label.pack(fill="both", expand=True)
        
        # Store reference to prevent garbage collection
        results_win._photo_ref = None
        
        def load_plot(*_):
            selected = plot_var.get()
            if not selected:
                return
            plot_path = results_dir / f"{selected}.png"
            if not plot_path.exists():
                return
            try:
                from PIL import Image, ImageTk
                img = Image.open(plot_path)
                # Scale to fit window while maintaining aspect ratio
                max_w, max_h = 850, 550
                img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                img_label.configure(image=photo, text="")
                results_win._photo_ref = photo  # Keep reference
            except ImportError:
                img_label.configure(text=f"PIL/Pillow not installed.\nPlot saved at:\n{plot_path}", image="")
            except Exception as e:
                img_label.configure(text=f"Error loading image: {e}", image="")
        
        plot_combo.bind("<<ComboboxSelected>>", load_plot)
        
        # Open folder button
        def open_folder():
            import os
            os.startfile(str(results_dir)) if os.name == 'nt' else os.system(f'open "{results_dir}"')
        
        ttk.Button(selector_frame, text="📁 Open Folder", command=open_folder, style="Compact.TButton").pack(side="right")
        
        # Load first plot
        if plot_names:
            results_win.after(100, load_plot)

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
    def enqueue_session_dir(self, p):
        self.session_dir_queue.put(p)
    def enqueue_data(self, d):
        self.data_queue.put(d)
    
    def poll_status(self):
        """Checks for new status messages every 200ms."""
        if not self.is_app_active: return

        while not self.status_queue.empty():
            self.log(self.status_queue.get_nowait())
        self.job_status = self.root.after(200, self.poll_status)
        
    def poll_session_dir(self):
        """Checks if a new session folder was created."""
        if not self.is_app_active: return
        while not self.session_dir_queue.empty():
            self.current_session_dir = self.session_dir_queue.get_nowait()
            self.log(f"Logging: {self.current_session_dir.name}")
        self.job_dir = self.root.after(500, self.poll_session_dir)
        
    def poll_plot(self):
        """Updates the graph every 50ms (20 FPS)."""
        if not self.is_app_active: return
        
        if self.current_session_dir: self.refresh_plot()
        
        self.job_plot = self.root.after(50, self.poll_plot)

    def poll_ports(self):
        """Checks for new serial ports every 2 seconds (THREADED)."""
        if not SERIAL_AVAILABLE: return
        
        # Avoid overlapping scans
        if self.port_scan_thread and self.port_scan_thread.is_alive():
            self.job_ports = self.root.after(2000, self.poll_ports)
            return

        self.port_scan_thread = threading.Thread(target=self._scan_ports_background, daemon=True)
        self.port_scan_thread.start()
        self.job_ports = self.root.after(2000, self.poll_ports)

    def _scan_ports_background(self):
        try:
            ports = serial.tools.list_ports.comports()
            self.root.after(0, lambda: self._update_ports_ui(ports))
        except: pass

    def _update_ports_ui(self, ports):
        try:
            current_selection = self.port_var.get()
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
                        self.port_combo.current(0)
        except: pass

    def refresh_plot(self):
        """
        Reads from RAM Buffer (Fast!) instead of Disk CSV.
        """
        stage = "drain"
        df = None

        new_data_count = 0
        try:
            # 1. Drain Queue into RAM Buffer
            while not self.data_queue.empty():
                self.live_data_buffer.append(self.data_queue.get_nowait())
                new_data_count += 1
            
            # Hard cap to prevent unbounded growth
            stage = "cap"
            if len(self.live_data_buffer) > self.buffer_cap:
                self.live_data_buffer = self.live_data_buffer[-self.buffer_cap:]
                
            if not self.live_data_buffer or new_data_count == 0:
                return

            # 2. Convert to DataFrame (OPTIMIZED: Only process the tail!)
            stage = "dataframe"
            points_to_process = self.live_data_buffer[-8000:]
            df = pd.DataFrame(points_to_process)
            
            # Rename match plotter expectations
            # Packet keys: t=time_str, s=song, w=walking, e=event
            df.rename(columns={"t": "time", "s": "song_bpm", "w": "walking_bpm", "e": "step_event"}, inplace=True)
            
            if "time" in df.columns:
                 df["seconds"] = df["time"].apply(_elapsed_to_seconds)
            else:
                 df["seconds"] = df.index

            # Ensure time ordering for plotting (engine can emit out-of-order timestamps)
            try:
                df = df.sort_values("seconds", kind="mergesort").reset_index(drop=True)
            except Exception:
                pass

            # Ensure boolean
            if "step_event" in df.columns:
                 # It comes as boolean from JSON, but just in case
                 df["step_event"] = df["step_event"].astype(bool)

            # Early exit if conversion failed
            if df.empty:
                return

            # Sliding time window: keep only recent seconds
            stage = "window"
            tmax = df["seconds"].max()
            if pd.isna(tmax):
                return

            window_start = tmax - self.view_window_sec
            keep_mask = df["seconds"] >= window_start
            if not keep_mask.all():
                df = df[keep_mask].reset_index(drop=True)
                
            # Downsample for rendering only (keep full buffer for history/export)
            stage = "downsample"
            if len(df) > self.max_live_points:
                step = max(1, len(df) // self.max_live_points)
                df_full = df
                df = df.iloc[::step].reset_index(drop=True)
                # Guarantee we keep the latest point for axis limits
                if not df.empty and not df_full.empty:
                    if df.iloc[-1]["seconds"] != df_full.iloc[-1]["seconds"]:
                        df = pd.concat([df, df_full.iloc[[-1]]], ignore_index=True)
            
            # Delegate to Plotter
            stage = "plotter_update"
            self.plotter.update(df)
            
            stage = "layout"
            if not self._did_tight_layout:
                try:
                    self.figure.tight_layout()
                    self._did_tight_layout = True
                except: 
                    pass
            
            stage = "draw"
            try:
                self.canvas.draw_idle()
            except Exception:
                pass

        except Exception as e:
            print(f"Plot Error ({stage}): {e}")
            return
        finally:
            pass

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
