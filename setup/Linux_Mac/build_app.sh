#!/bin/bash

# Parse command line arguments
if [ "$1" = "--clean" ] || [ "$1" = "-c" ]; then
    # Navigate to project root
    cd "$(dirname "$0")/../.." || exit 1
    
    # Clean build artifacts
    echo "========================================"
    echo "  Cleaning Build Artifacts"
    echo "========================================"
    echo ""
    
    # Kill any running instances of the application
    echo "Closing any running BrainMusicSync instances..."
    pkill -f "BrainMusicSync" 2>/dev/null || true
    sleep 1
    
    # Clean build artifacts
    if [ -d "build" ]; then
        rm -rf build 2>/dev/null
        if [ -d "build" ]; then
            echo "Warning: Could not fully remove build/"
        else
            echo "Removed: build/"
        fi
    fi
    
    if [ -d "dist" ]; then
        rm -rf dist 2>/dev/null
        if [ -d "dist" ]; then
            echo "Error: Could not remove dist/ - files may be in use"
            echo "Please close any running instances of BrainMusicSync"
            read -p "Press Enter to exit..."
            exit 1
        else
            echo "Removed: dist/"
        fi
    fi
    
    # Clean Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    echo "Removed: __pycache__ directories"
    
    # Clean .pyc files
    find . -type f -name "*.pyc" -delete 2>/dev/null
    echo "Removed: .pyc files"
    
    echo ""
    echo "========================================"
    echo "  Clean complete!"
    echo "========================================"
    echo ""
    read -p "Press Enter to exit..."
    exit 0
fi

echo "========================================"
echo "  Brain Music Sync - Build System"
echo "  Building Portable Application"
echo "========================================"
echo ""

# Navigate to project root (two levels up from setup/Linux_Mac/)
cd "$(dirname "$0")/../.." || exit 1

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    echo "Please install Python 3.8+ from python.org or your package manager"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "[Step 1/5] Python found"
python3 --version
echo ""

# Check/create virtual environment
echo "[Step 2/5] Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating new virtual environment..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo ""

# Install dependencies
echo "[Step 3/5] Installing dependencies..."
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies"
    read -p "Press Enter to exit..."
    exit 1
fi
echo "Dependencies installed successfully"
echo ""

# Clean previous builds
echo "[Step 4/5] Cleaning previous builds..."

# Kill any running instances of the application
pkill -f "BrainMusicSync" 2>/dev/null || true
sleep 1

if [ -d "build" ]; then
    rm -rf build 2>/dev/null
    if [ -d "build" ]; then
        echo "Warning: Could not fully clean build/ folder"
    fi
fi

if [ -d "dist" ]; then
    rm -rf dist 2>/dev/null
    if [ -d "dist" ]; then
        echo "Error: Could not clean dist/ folder - files may be in use"
        echo "Please close any running instances of BrainMusicSync and try again"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi
echo ""

# Build with PyInstaller
echo "[Step 5/5] Building executable..."
echo "This may take 3-5 minutes..."
echo ""
pyinstaller --clean setup/build.spec
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] PyInstaller build failed!"
    read -p "Press Enter to exit..."
    exit 1
fi
echo ""
echo "Executable built successfully!"
echo ""

# Copy MIDI files
echo "Copying MIDI files..."
if [ -d "midi_files" ]; then
    mkdir -p "dist/BrainMusicSync/midi_files"
    cp -r midi_files/*.mid "dist/BrainMusicSync/midi_files/" 2>/dev/null || true
    echo "MIDI files copied"
fi
echo ""

# Copy Default logs
echo "Copying Default logs..."
if [ -d "server/logs/Default" ]; then
    mkdir -p "dist/BrainMusicSync/server/logs/Default"
    cp -r "server/logs/Default/"* "dist/BrainMusicSync/server/logs/Default/" 2>/dev/null || true
    echo "Default logs copied"
fi
echo ""

echo "========================================"
echo "  Build complete!"
echo "========================================"
echo ""
echo "Application: dist/BrainMusicSync/BrainMusicSync"
echo ""
echo "To run:"
echo "  cd dist/BrainMusicSync"
echo "  ./BrainMusicSync"
echo ""
echo "To create desktop shortcut:"
echo "  Linux: Create .desktop file in ~/.local/share/applications/"
echo "  macOS: Drag to Applications folder"
echo ""
read -p "Press Enter to exit..."

