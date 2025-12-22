# Brain-Music Sync

**Neuro-Adaptive Music Controller** - A real-time system that synchronizes music tempo with walking speed.

## Overview

This project uses foot-mounted sensors (ESP32) to detect walking cadence and dynamically adjusts MIDI playback tempo to match the user's pace. Designed for gait rehabilitation and research applications.

## Project Structure

```
├── server/              # Python backend
│   ├── main.py          # Core orchestrator
│   ├── gui_app.py       # Tkinter GUI
│   └── utils/           # Helper modules
│       ├── BPM_estimation.py
│       ├── comms.py
│       ├── logger.py
│       ├── midi_player.py
│       ├── plotter.py
│       ├── process_manager.py
│       └── safety.py
├── ESP32/               # Firmware for sensors
├── research/            # KNN prediction experiments
├── midi_files/          # Sample MIDI tracks
└── logs/                # Session recordings
```

## Quick Start

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the GUI:**
   ```bash
   cd server
   python gui_app.py
   ```

3. **Or run headless (CLI):**
   ```bash
   cd server
   python main.py --serial-port COM5
   ```

## Features

- **Real-time BPM Tracking:** Asymmetric smoothing for natural tempo transitions
- **Live Visualization:** Matplotlib-based dashboard
- **Session Logging:** CSV export with timestamps
- **Safety Decorators:** Crash-resistant error handling
- **KNN Research Module:** Predictive BPM estimation (experimental)

## Hardware

- ESP32 with accelerometer/foot sensor
- Serial connection at 115200 baud

## License

Part of ICST - The Interdisciplinary Center for Smart Technologies, Technion.
https://icst.cs.technion.ac.il/
