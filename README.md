# Researching the effect of music on walking Project by: Sleeman Nabwani, Rund Sobih & Samir Zarka.

This project provides a real-time research platform for investigating music-based gait cueing, with a focus on Parkinson’s-related mobility challenges. By enabling tempo alignment between music and walking pace, it supports controlled evaluation of synchronization strategies and their potential therapeutic value. The system was developed for Professor Eitan Globerson’s research.

# Details about the project:

This is a Neuro-Adaptive Music Controller that lets users synchronize their music to their movement. The system uses force-sensitive resistors (FSRs) on the feet to detect steps, sending this data via ESP-NOW to a receiver ESP2, which then forwards it to a Python backend.
The backend calculates the BPM in real-time and scales the playback speed of MIDI files accordingly. It also features a LGBM-based predictor for smoother tempo transitions and a manual mode for therapist control.

## 1. Setup
Run the setup script for your operating system. This will automatically create a virtual environment and **install all required dependencies** listed in `requirements.txt` (e.g., pandas, matplotlib, scikit-learn).
- **Windows:** Run `setup_env.bat`
- **Linux/Mac:** Run `setup_env.sh` (ensure permissions: `chmod +x setup_env.sh`)

## 2. Running
Launch the application using the start script:
- **Windows:** Run `start_app.bat`
- **Linux/Mac:** Run `start_app.sh`


**System Diagram:**

<img width="800" height="400" alt="image" src="https://github.com/user-attachments/assets/2294b6fa-a221-4d61-a802-3628dbb9f91d" />



**Hardware diagram:**

<img width="800" height="400" alt="image" src="https://github.com/user-attachments/assets/d892eb28-dcfd-45ba-8cf6-4d3fa3f5b19e" />


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
