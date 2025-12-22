# Brain-Music Interface: Technical Deep Dive

This document provides a comprehensive, line-by-line breakdown of the system's execution flow. It describes exactly how the code moves from the user's "Start" click to the final audio output.

---

## 1. The Startup Sequence (The "Checklist")

### Phase 1: GUI Initialization (`gui_app.py`)
1.  **Entry Point**: The user runs `python gui_app.py`.
2.  **`GuiApp.__init__`**:
    *   Creates the Tkinter window (`root`).
    *   **Theme Setup**: Defines the "Slate" color palette (`self.P`).
    *   **Layout**: Builds the sidebar (Controls) and the main area (Plot).
    *   **Plotter Init**: Instantiates `LivePlotter` (but doesn't start plotting yet).
    *   **Button Binding**: Binds `self.btn_start` to `self.start_session()`.

### Phase 2: The "Start" Command
When the user clicks **START SESSION**:
1.  **`start_session()`**:
    *   **Validation**: Checks if a COM port is selected and if the MIDI file exists.
    *   **Config Collection**: Reads "Smoothing Window" (e.g., 6) and "Stride" (e.g., 1) from the input boxes.
    *   **Process Launch**: Calls `SubprocessManager(...)`.

### Phase 3: The Subprocess Launch (`SubprocessManager`)
This class is the "manager" of the invisible backend.
1.  **`__init__`**:
    *   Constructs a command list: `[python.exe, main.py, song.mid, --port, COM5, ...]`.
    *   **`subprocess.Popen(...)`**:
        *   `cwd=server/`: **CRITICAL**. Ensures `main.py` runs inside the server folder so it can find its imports.
        *   `stdout=PIPE`: Captures all `print()` outputs from `main.py`.
        *   `stdin=PIPE`: Allows sending commands (like "QUIT") to `main.py`.
    *   **Threads**: Starts two background threads:
        *   `_read_stdout`: To catch data packets.
        *   `_read_stderr`: To catch Python crash errors.

---

## 2. The Backend lifecycle (`main.py`)

This script runs silently in the background. It is the "Engine".

### Step 1: Imports & Setup
1.  **Imports**: Loads `midi_player`, `serial`, `logger`.
2.  **Argparse**: Parses the flags sent by the GUI (e.g., `--smoothing 6`).
3.  **`main()` Entry**:
    *   **`Logger()`**: Creates the session folder (e.g., `logs/Default/session_2025...`).
    *   **`print(SESSION_DIR:...)`**: Tells the GUI where the logs are being saved.

### Step 2: The Handshake (`comms.py`)
Before playing music, the PC must ensure the Shoe (ESP32) is ready.
1.  **`session_handshake()`**:
    *   **`ser.write(b"RESET\n")`**: Asks ESP32 to clear its state.
    *   **Wait**: Loops 5 times waiting for `ACK,RESET`.
    *   **`ser.write(b"START\n")`**: Tells ESP32 to begin streaming sensor data.
    *   **Wait**: Loops 5 times waiting for `ACK,START`.

### Step 3: Initialization
1.  **`MidiBeatSync()`**:
    *   Loads the MIDI file using `mido`.
    *   scans for the initial Tempo (e.g., 120 BPM).
    *   Sets `walkingBPM = 120`.
2.  **`BPM_estimation()`**:
    *   Initializes the smoothing logic (Attack/Decay alphas).
3.  **`player.play()`**:
    *   Starts the internal clock. The music is now technically "playing" at the default speed.

---

## 3. The Main Execution Loop (The "Heartbeat")

This `while True:` loop in `main.py` runs as fast as possible (limited by serial data arrival).

### A. The Input (`ser.readline`)
*   **Blocking Read**: The code stops at `ser.readline()` until the ESP32 sends a full line (terminated by `\n`).
*   **Data Format**: It receives `TIMESTAMP, FOOT_ID, INTERVAL, BPM`.
    *   Example: `10500, 1, 600, 100` (Time 10.5s, Left Foot, 600ms gap, 100 Raw BPM).

### B. The Decision (`BPM_estimation.py`)
1.  **`register_step(100)`**:
    *   The `BPM_estimation` class records this new Raw BPM as the **Target BPM**.
    *   It does **NOT** jump the music to 100 BPM instantly. That would sound jerky.

2.  **`update_bpm()`**:
    *   Calculates the **Difference**: `Target (100) - Current (120) = -20`.
    *   Applies **Smoothing** (`alpha_down`):
        *   `Step = -20 * 0.025 * dt`.
        *   New BPM becomes `119.5`.
    *   **Result**: The music slows down *slightly* towards the target.

### C. The Actuation (`midi_player.py`)
1.  **`set_BPM(119.5)`**:
    *   Calculates `TempoFactor = OriginalBPM / NewBPM`.
    *   This factor is used to scale the `time.sleep()` duration between MIDI notes.
    *   **Effect**: The notes play slightly further apart (slower).

### D. The Output (`logger.py`)
1.  **`log_csv(...)`**: Appends the specific step data to `session.csv` on the hard drive.
2.  **`log_data(...)`**:
    *   Constructs a JSON object: `{"time": 10.5, "bpm": 119.5, "target": 100}`.
    *   **`print("DATA_PACKET:...")`**: Flushes this string to `stdout`.
    *   This is how the data jumps from the background process to the GUI.

---

## 4. The Visualization Loop (`gui_app.py`)

### Thread A: The Listener (`SubprocessManager._read_stdout`)
1.  Sits in a `while` loop reading lines from `main.py`.
2.  Sees `DATA_PACKET:{...}`.
3.  Parses the JSON.
4.  **`data_callback(data)`**: Pushes the data into a thread-safe **Queue** (`gui_app.data_queue`).

### Thread B: The Plotter (`GuiApp.poll_plot`)
1.  **`root.after(100, poll_plot)`**: runs every 100ms on the main UI thread.
2.  **`queue.empty()`**: Checks if new data arrived.
3.  **`LivePlotter.update()`**:
    *   Takes the new points (BPM 119.5).
    *   **`line.set_data()`**: Updates the Y-coordinates of the matplotlib graph.
    *   **`canvas.draw()`**: Repaints the blue line.

---

## 5. The Shutdown

1.  User clicks **STOP**.
2.  `gui_app.py` writes `QUIT\n` to the subprocess Stdin.
3.  `main.py`'s `stdin_listener` thread sees `QUIT`.
4.  It sets `stop_event`.
5.  The Main Loop breaks.
6.  `player.close()`: Stops the MIDI port.
7.  `ser.close()`: Frees the COM port.
8.  `main.py` exits.
9.  `gui_app.py` sees the process die and resets the GUI buttons.
