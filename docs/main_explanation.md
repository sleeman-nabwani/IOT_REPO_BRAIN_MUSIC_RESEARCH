# Deep Dive: `main.py`

This file is the **Backbone** of the backend. It is a single script that coordinates the Sensor, the Music, and the Logger. It has no window; it runs entirely in the console (or hidden by the GUI).

---

## 1. Imports and Setup
*   **`sys`, `os`**: Standard system libraries for file paths and exiting.
*   **`threading`**: Used to run the "Stdin Listener" (see below) without stopping the music.
*   **`time`**: For timing the loop and sleeps (essential for music precision).
*   **`serial`**: The `pyserial` library, the only way Python can talk to the USB port (ESP32).
*   **`mido`**: The library that parses MIDI files and sends messages to the Windows Synthesizer.

## 2. Argument Parsing (`parse_args`)
This function allows the GUI to configure the backend without changing code.
*   **`midi_path`**: The song to play (passed by GUI file picker).
*   **`--serial-port`**: Critical. Which USB port is the shoe on? (e.g., COM5).
*   **`--smoothing`**: How "steady" the BPM should be (Window Size).
*   **`--stride`**: How often to update the BPM (e.g., every step vs every 4 steps).
*   **`--session-name`**: Custom name for the log folder.

## 3. The `main()` Function: Step-by-Step

### Phase A: Bootup
1.  **`Logger()`**: The FIRST thing it does is create the log folder.
    *   It prints `SESSION_DIR:...` to `stdout`.
    *   **Why?** The GUI is listening for this line so it knows where to find the CSV files later.
2.  **`MidiBeatSync(midi_path)`**:
    *   Opens the MIDI file.
    *   Scans every track to find the FIRST `SetTempo` event.
    *   Saves this as `self.songBPM`.
3.  **`start_playback()`**: The music starts immediately, but silently (or at default speed).

### Phase B: The Connection
1.  **`serial.Serial(port)`**: Tries to grab the COM port.
    *   If it fails (e.g., in use), it crashes (caught by try/except).
2.  **`session_handshake()`**:
    *   Sends `RESET` to ESP32.
    *   Waits for `ACK,RESET`.
    *   Sends `START` to ESP32.
    *   Waits for `ACK,START`.
    *   **Purpose**: ensures we don't start reading midway through a packet.

### Phase C: The Stdin Listener (The "Third Ear")
*   **Code**: `threading.Thread(target=stdin_listener)`
*   **Why?** The `while True` loop is busy reading the Serial Port. It can't listen to the Keyboard/GUI.
*   **How**: This separate thread sits blocked at `sys.stdin.readline()`.
*   **Function**: When it hears `QUIT`, it signals the main loop to stop. When it hears `SET_MANUAL_BPM:100`, it changes the music instantly.

### Phase D: The Main Loop (The "Heart")
Reference Line: `while True:`

1.  **`check_stop_event()`**: Did the user press Stop? If yes, break.
2.  **`process_command_queue()`**: Did the Stdin Thread receive a command?
    *   If `SET_ALPHA_UP:0.1` -> Update `BPM_estimation`.
    *   If `QUIT` -> Break.
3.  **`check_music_end()`**: `next(playback)`.
    *   If the song ends (`StopIteration`), it restarts (`player.play()`).
4.  **`update_bpm()`**: ONE OF THE MOST IMPORTANT LINES.
    *   Calls `BPM_estimation.update_bpm()`.
    *   This gradually slides the `walkingBPM` towards the `targetBPM`.
    *   It does this *every single loop* (100 times/sec) to make the slide smooth.
5.  **`ser.readline()`**:
    *   **Blocking**: The code WAITS here for the Shoe to speak.
    *   **Raw Data**: `12000, 1, 600, 100` (Timestamp, Foot, Interval, BPM).
6.  **`logger.log_csv()`**: Saves the raw data to disk.
7.  **`logger.log_data()`**: Prints `DATA_PACKET:{...}` to `stdout` for the GUI.

### Phase E: Cleanup
*   `player.close()`: Stops MIDI.
*   `ser.close()`: Release USB.
*   `print("EXIT_CLEAN")`: Tells GUI "I died peacefully".
