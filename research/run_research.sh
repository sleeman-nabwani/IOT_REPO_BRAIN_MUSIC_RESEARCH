#!/bin/bash

# ============================================
# Research Pipeline Runner (Linux/Mac)
# ============================================

echo
echo "========================================"
echo "  Brain-Music Research Pipeline"
echo "========================================"
echo

# Navigate to project root (parent of current script directory)
# Resolving absolute path to the directory containing this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Assuming script is in research/, so project root is one up
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate Virtual Environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "Virtual environment activated."
else
    echo "Error: Virtual environment '.venv' not found."
    echo "Please run './setup_env.sh' first!"
    exit 1
fi

# Install scikit-learn if missing
if ! pip show scikit-learn > /dev/null 2>&1; then
    echo "Installing scikit-learn..."
    pip install scikit-learn
fi

# Navigate to research folder
cd research

echo
echo "[1/2] Analyzing session data..."
echo
python analyze_data.py
if [ $? -ne 0 ]; then
    echo "ERROR: analyze_data.py failed!"
    exit 1
fi

echo
echo "----------------------------------------"
echo

echo "[2/2] Training KNN model..."
echo
python train_knn.py
if [ $? -ne 0 ]; then
    echo "ERROR: train_knn.py failed!"
    exit 1
fi

echo
echo "========================================"
echo "  Pipeline Complete!"
echo "========================================"
echo
echo "Generated files in research/results/:"
echo "  - plots/bpm_distribution.png"
echo "  - plots/knn_performance.png"
echo "  - models/knn_model.joblib"
echo

read -p "Press Enter to exit..."
