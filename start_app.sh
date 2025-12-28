#!/bin/bash

# ======================================================================================
# BRAIN MUSIC INTERFACE - LAUNCHER SCRIPT (Linux/Mac)
# ======================================================================================

echo "=================================================="
echo "      STARTING BRAIN MUSIC INTERFACE..."
echo "=================================================="
echo

# Check for Virtual Environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment '.venv' not found."
    echo "Please run './setup_env.sh' first!"
    exit 1
fi

# Launch Application
echo "Launching GUI..."
# Ensure we are in the directory of the script or the project root
# For simplicity, assuming the script is run from project root as ./start_app.sh
python server/gui_app.py

if [ $? -ne 0 ]; then
    echo
    echo "Application crashed or exited with error."
    read -p "Press Enter to exit..."
fi
