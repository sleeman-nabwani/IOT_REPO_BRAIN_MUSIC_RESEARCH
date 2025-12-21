# System Architecture & Workflow Walkthrough

This document explains how your Brain-Music Interface works, from the hardware sensors to the music generation.

## High-Level Overview

This system is a **closed-loop biofeedback controller**. It detects a user's walking tempo (steps per minute) and dynamically adjusts the playback speed of a MIDI song to match their pace in real-time.

### The Core Loop
1.  **SENSE**: ESP32 detects a step and calculates the interval.
2.  **ESTIMATE**: Server calculates a smooth Target BPM.
3.  **ADJUST**: MIDI Player speeds up or slows down the music.
4.  **FEEDBACK**: User hears the music and unconsciously adjusts their walking to match.

---

## Detailed Workflow

### 1. The Hardware Layer (ESP32)
*   **Role**: Sensor & Pre-processor.
*   **Action**: Detects heel strikes (steps).
*   **Communication**: Sends a packet to the PC via USB Serial every time a step occurs.
    *   Format: `timestamp, foot_id, interval_ms, raw_bpm`

### 2. The GUI Layer (`gui_app.py`)
*   **Role**: Command Center.
*   **Action**: 
    *   User selects the **MIDI Song** and **Serial Port**.
    *   Starts `main.py` as a background process (Subprocess).
    *   **Visualization**: Plots the live BPM data (Walking vs. Music) using `plotter.py`.
    *   **Controls**: Allows tuning "Smoothing" (Attack/Decay) and "Manual Mode" on the fly.

### 3. The Backend Engine (`main.py`)
*   **Role**: Orhcestrator.
*   **Action**:
    *   Connects to the Serial Port.
    *   Plays the MIDI file using `midi_player.py`.
    *   Feed step data into the BPM Estimator.

### 4. BPM Estimation Logic (`BPM_estimation.py`)
This is the "Brain" of the system. It ensures the music doesn't jump erratically with every mis-step.

*   **Target BPM**: The raw speed calculated from the last few steps.
*   **Current BPM**: The speed the music is currently playing at.
*   **Smoothing Algorithm**:
    *   The system gradually slides the **Current BPM** towards the **Target BPM**.
    *   **Attack (Speed Up)**: How fast it reacts when you walk faster. (Configurable).
    *   **Decay (Slow Down)**: How fast it drops when you stop. (Configurable).
    *   *Adaptive Boost*: If you sprint (Target >>> Current), it temporarily increases sensitivity to catch up fast.

### 5. Post-Session Analysis (`plotter.py`)
*   When you stop the session, the system saves a log (`session_data.csv`).
*   It generates a **BPM Tracking Plot** showing:
    *   **Blue Line**: Your walking speed.
    *   **Orange Line**: The music speed.
    *   **Green Dots**: Exact moments you stepped.
    *   **Sync Error**: How closely the music matched your gait.

---

## File Structure Map
*   **`main.py`**: Entry point. Runs the loop.
*   **`comms.py`**: Handles raw Serial communication (handshake/data).
*   **`BPM_estimation.py`**: Math logic for smoothing/targeting.
*   **`midi_player.py`**: Wrapper for `mido` library to play notes.
*   **`gui_app.py`**: The visual frontend (Tkinter).
*   **`plotter.py`**: Matplotlib logic for graphs.
*   **`logger.py`**: Handles file I/O (saving CSVs).
