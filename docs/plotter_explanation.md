# Deep Dive: `plotter.py`

This file handles the visual graph. It uses **Matplotlib**, a powerful science graphing tool, but tweaks it to run at "Video Game Speed" (60fps).

---

## 1. Helper Functions
### `_elapsed_to_seconds(time_str)`
*   **Input**: `"00:01:05.500"`
*   **Logic**: Splits by `:` and calculates `Hours*3600 + Minutes*60 + Seconds`.
*   **Why?**: The log file stores human-readable time, but the graph needs raw numbers (X-axis).

### `find_latest_session_folder()`
*   Used by `gui_app.py` on startup to possibly load the last session.
*   Scans `logs/` recursively to find the folder with the newest timestamp.

## 2. The `LivePlotter` Class
This class manages the specific Matplotlib "Artists" (Lines and Canvases).

### `__init__` (The Setup)
1.  **Arguments**: It takes an `ax` (The Axes object) and `param` (Theme colors).
2.  **Lines**:
    *   `self.line_walking`: The Blue line (Current BPM).
    *   `self.line_song`: The Green/Yellow line (Target BPM).
3.  **Optimization**: `self.ax.draw_artist(line)`. It tells Matplotlib "We will draw these manually, don't auto-refresh".

### `update(df)` (The Animation Frame)
*   **Input**: A Pandas DataFrame containing the last N seconds of data.
*   **Step 1: Convert Data**:
    *   `x = df['seconds']`
    *   `y1 = df['walking_bpm']`
*   **Step 2: Update Geography**:
    *   `self.line_walking.set_data(x, y1)`: Updates the internal coordinates of the line.
*   **Step 3: Auto-Scale**:
    *   `self.ax.set_xlim(...)`: Moves the "Camera" to follow the new time.
    *   `self.ax.set_ylim(...)`: Zooms in/out so the line fits vertically.
*   **Step 4: The Draw Broadcast**:
    *   This function *finishes* by telling the GUI canvas it's ready to be painted.

## 3. The "Post-Session" Plot (`generate_post_session_plot`)
*   **Trigger**: Called when user presses "STOP SESSION".
*   **Logic**:
    1.  Reads the FULL `session.csv`.
    2.  Creates a high-resolution version of the graph.
    3.  Adds a "Delta Bar Chart" (Difference between Foot Interval and Music Beat).
    4.  Saves it as `post_session_plot.png` in the log folder.
