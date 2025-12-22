# Deep Dive: `logger.py`

This class handles all data storage and broadcasting. It is designed to be "Thread-Safeish" and robust against crashes.

---

## 1. Helper Functions
### `get_next_session_folder(base_logs_dir)`
*   **Purpose**: Prevention of overwriting.
*   **Logic**:
    1.  Looks at `logs/Default/`.
    2.  Finds all folders named `session_YYYY-MM-DD_N`.
    3.  Finds the highest `N` (e.g., if `..._2` exists, it returns `3`).
*   **Result**: Every session gets a unique, safe directory.

## 2. The `Logger` Class

### `__init__` (The Setup)
1.  **Session Naming**:
    *   If user provided specific name (e.g. "Test1"), it creates `logs/Test1`.
    *   If not, it defaults to `logs/Default`.
2.  **Timestamp**: Generates `2025-12-21...`.
3.  **Creation**: `os.makedirs(self.path)` creates the physical folder on the hard drive.
4.  **CSV Headers**: It immediately creates `session.csv` and writes the header row: `Timestamp, WalkingBPM, SongBPM`.

### `log(message)` (Text Logging)
*   **Console**: Prints the message to the screen (formatted with time).
*   **File**: Appends the message to `session_log.txt`.
*   **Flush**: Calls `sys.stdout.flush()` to ensure the text appears instantly in the GUI console, rather than checking buffer.

### `log_data(timestamp, walking_bpm, song_bpm)` (The Dual Stream)
This is the critical function that saves data AND updates the GUI graph.

#### Stream 1: Hard Drive (Safe)
*   Opens `session.csv` in append mode (`"a"`).
*   Writes `10.5, 120, 100` to the end of the file.
*   This ensures that if the app crashes 1ms later, this data point is saved forever.

#### Stream 2: RAM Broadcast (Fast)
*   Constructs a Python Dictionary: `data = {"time": ..., "bpm": ...}`.
*   Converts it to JSON text.
*   **The Magic Line**: `print(f"DATA_PACKET:{json_str}")`.
*   **Result**: This text flies out of `stdout`, is caught by `gui_app.py`, and turns into a blue dot on the graph 5ms later.
