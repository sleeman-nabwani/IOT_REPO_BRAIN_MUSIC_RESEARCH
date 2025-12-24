#!/bin/bash

# ======================================================================================
# BRAIN MUSIC INTERFACE - SETUP WIZARD (Linux/Mac)
# ======================================================================================

# SETUP NOTE:
# If you want to do a full test run on Windows (using WSL), create a separate copy of 
# your project folder (e.g., test_linux), open WSL in that folder, and run it there.
# Do NOT run this in the same folder as your Windows setup, or it will break your .venv!
# BRAIN MUSIC INTERFACE - SETUP WIZARD (Linux/Mac)
# ======================================================================================

echo "=================================================="
echo "      BRAIN MUSIC INTERFACE - SETUP WIZARD"
echo "=================================================="
echo
echo "This script will:"
echo "  1. Create a Python Virtual Environment (.venv)"
echo "  2. Upgrade pip"
echo "  3. Install all dependencies"
echo "  4. Train initial KNN model (if session data exists)"
echo
read -p "Press Enter to continue..."

# 1. Create Virtual Environment
echo
echo "[1/4] Creating virtual environment..."

PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
        echo "python3 not found, using python..."
    else
        echo "Error: Neither 'python3' nor 'python' found."
        echo "Please install Python 3."
        exit 1
    fi
fi

if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
    if [ $? -ne 0 ]; then
        echo "Error creating venv!"
        exit 1
    fi
else
    echo "Virtual environment already exists, skipping creation."
fi

# 2. Activate Environment
echo
echo "[2/4] Activating environment and upgrading pip..."
source .venv/bin/activate
echo "Upgrading pip..."
pip install --upgrade pip

# 3. Install Dependencies
echo
echo "[3/4] Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error installing dependencies!"
    exit 1
fi
echo "Dependencies installed successfully."

# 4. Train Initial KNN Model
echo
echo "[4/4] Training KNN model..."

if [ -d "server/logs/Default" ]; then
    cd research
    python analyze_data.py
    python train_knn.py
    cd ..
else
    echo "No session data found yet. KNN will train after your first session."
fi

echo
echo "=================================================="
echo "      SETUP COMPLETE!"
echo "=================================================="
echo
echo "You can now use './start_app.sh' to run the application."
echo "Note: You may need to run 'chmod +x setup_env.sh' and 'chmod +x start_app.sh' first."
echo
