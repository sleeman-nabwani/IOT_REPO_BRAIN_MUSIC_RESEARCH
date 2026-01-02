# Researching the effect of music on walking Project by: Sleeman Nabwani, Rund Sobih & Samir Zarka.

This project provides a real-time research platform for investigating music-based gait cueing, with a focus on Parkinson’s-related mobility challenges. By enabling tempo alignment between music and walking pace, it supports controlled evaluation of synchronization strategies and their potential therapeutic value. The system was developed for Professor Eitan Globerson’s research.

# Details about the project:

This is a Neuro-Adaptive Music Controller that lets users synchronize their music to their movement. The system uses force-sensitive resistors (FSRs) on the feet to detect steps, sending this data via ESP-NOW to a receiver ESP2, which then forwards it to a Python backend.
The backend calculates the BPM in real-time and scales the playback speed of MIDI files accordingly. It also features a LGBM-based predictor for smoother tempo transitions and a manual mode for therapist control.

# Key Features:
* **Neuro-Adaptive Synchronization**: Real-time adjustment of music tempo (BPM) to match walking cadence.
* **LGBM Prediction Control**: Advanced Machine Learning model (LightGBM) for smooth, jitter-free tempo transitions.
* **Wireless Low-Latency**: Utilizes **ESP-NOW** protocol for instant communication between foot sensors and the main unit.
* **Therapist Dashboard**: Python-based GUI for real-time monitoring, manual BPM override, and session management.
* **Gait Analysis & Logging**: Records high-resolution step data and session metrics for research analysis.

# Installation & Usage:

**1. Setup:**

Run the setup script for your operating system. This will automatically create a virtual environment and **install all required dependencies** listed in `requirements.txt` (e.g., pandas, matplotlib, scikit-learn).
- **Windows:** Run `setup_env.bat`
- **Linux/Mac:** Run `setup_env.sh` (ensure permissions: `chmod +x setup_env.sh`)

**2. Running:**

Launch the application using the start script:
- **Windows:** Run `start_app.bat`
- **Linux/Mac:** Run `start_app.sh`


**System Overview:**

<img width="800" height="400" alt="image" src="https://github.com/user-attachments/assets/991cdfc8-dc72-4c4c-866a-1f1403c760b4" />



**Hardware diagram:**

<img width="800" height="400" alt="image" src="https://github.com/user-attachments/assets/dcc5a861-dedf-41be-a67a-22c9d6cbb480" />


# libraries:
**Arduino:**
- WiFi
- esp_wifi
- esp_now

**Python:**
*(Note: These are installed automatically by `setup_env.bat`/`.sh`)*
- pandas: `pip install pandas`
- matplotlib: `pip install matplotlib`
- pyserial: `pip install pyserial`
- numpy: `pip install numpy`
- mido: `pip install mido`
- python-rtmidi: `pip install python-rtmidi`
- scikit-learn: `pip install scikit-learn`
- lightgbm: `pip install lightgbm`
- optuna: `pip install optuna`
- xgboost: `pip install xgboost`
- catboost: `pip install catboost`


# Folder description:
* **ESP32**: Firmware source code for the foot sensors (sender) and the receiver unit.
* **server**: The core Python backend, GUI application, and orchestration logic.
* **research**: Machine learning experiments (LGBM), data analysis tools, and model training scripts.
* **midi_files**: Collection of MIDI tracks used for adaptive playback.
* **logs**: Directory for storing session recordings and CSV data logs.


IoT Project 236333, ICST - The Interdisciplinary Center for Smart Technologies, Technion.
https://icst.cs.technion.ac.il/
