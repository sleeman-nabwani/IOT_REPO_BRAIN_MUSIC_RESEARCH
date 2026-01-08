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

echo "[Step 1/6] Python found"
python3 --version
echo ""

# Check and install tkinter if needed (macOS Homebrew Python issue)
echo "[Step 2/6] Checking tkinter availability..."
if ! python3 -c "import tkinter" &> /dev/null; then
    echo "⚠ tkinter not found - this is required for the GUI"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Check if using Homebrew Python by examining the python path
        PYTHON_PATH=$(which python3)
        if [[ "$PYTHON_PATH" == *"homebrew"* ]] || [[ "$PYTHON_PATH" == *"Cellar"* ]] || [[ "$PYTHON_PATH" == *"/opt/homebrew/"* ]]; then
            echo "Detected Homebrew Python at: $PYTHON_PATH"
            
            # Check if brew is installed
            if ! command -v brew &> /dev/null; then
                echo "[ERROR] Homebrew is installed but 'brew' command not found"
                echo "Please ensure Homebrew is properly configured in your PATH"
                read -p "Press Enter to exit..."
                exit 1
            fi
            
            echo "Installing python-tk via Homebrew..."
            
            # Get Python version
            PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            echo "Python version: ${PY_VERSION}"
            
            brew install python-tk@${PY_VERSION}
            
            if [ $? -ne 0 ]; then
                echo ""
                echo "[ERROR] Failed to install python-tk"
                echo "Please manually install it with: brew install python-tk@${PY_VERSION}"
                read -p "Press Enter to exit..."
                exit 1
            fi
            
            # Verify installation
            if python3 -c "import tkinter" &> /dev/null; then
                echo "✓ tkinter installed successfully"
            else
                echo "[ERROR] tkinter installation failed"
                echo "Please try manually: brew install python-tk@${PY_VERSION}"
                read -p "Press Enter to exit..."
                exit 1
            fi
        else
            echo "[ERROR] tkinter is not available"
            echo "Please install Python with tkinter support:"
            echo "  Option 1: Install from python.org (includes tkinter)"
            echo "  Option 2: If using Homebrew Python: brew install python-tk@3.x"
            read -p "Press Enter to exit..."
            exit 1
        fi
    else
        # Linux
        echo "[ERROR] tkinter is not available"
        echo "Please install tkinter:"
        echo "  Ubuntu/Debian: sudo apt-get install python3-tk"
        echo "  Fedora: sudo dnf install python3-tkinter"
        echo "  Arch: sudo pacman -S tk"
        read -p "Press Enter to exit..."
        exit 1
    fi
else
    echo "✓ tkinter is available"
fi
echo ""

# Check/create virtual environment
echo "[Step 3/6] Setting up virtual environment..."
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
echo "[Step 4/6] Installing dependencies..."
echo "This may take a few minutes on first run..."
python -m pip install --upgrade pip --quiet

# Install requirements
echo "Installing required packages..."
pip install -r requirements.txt

# Explicitly install PyInstaller
echo "Installing PyInstaller..."
pip install pyinstaller

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies"
    read -p "Press Enter to exit..."
    exit 1
fi
echo "✓ All dependencies installed successfully"
echo ""

# Clean previous builds
echo "[Step 5/6] Cleaning previous builds..."

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
echo "[Step 6/6] Building executable..."
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
echo "✓ Executable built successfully!"
echo ""

# Copy MIDI files
echo "Copying MIDI files..."
if [ -d "midi_files" ]; then
    if [[ "$OSTYPE" == "darwin"* ]] && [ -d "dist/BrainMusicSync.app" ]; then
        # For macOS app bundle
        mkdir -p "dist/BrainMusicSync.app/Contents/MacOS/midi_files"
        cp -r midi_files/*.mid "dist/BrainMusicSync.app/Contents/MacOS/midi_files/" 2>/dev/null || true
    else
        # For regular dist folder
        mkdir -p "dist/BrainMusicSync/midi_files"
        cp -r midi_files/*.mid "dist/BrainMusicSync/midi_files/" 2>/dev/null || true
    fi
    echo "✓ MIDI files copied"
fi
echo ""

# Copy Default logs
echo "Copying Default logs..."
if [ -d "server/logs/Default" ]; then
    if [[ "$OSTYPE" == "darwin"* ]] && [ -d "dist/BrainMusicSync.app" ]; then
        # For macOS app bundle
        mkdir -p "dist/BrainMusicSync.app/Contents/MacOS/server/logs/Default"
        cp -r "server/logs/Default/"* "dist/BrainMusicSync.app/Contents/MacOS/server/logs/Default/" 2>/dev/null || true
    else
        # For regular dist folder
        mkdir -p "dist/BrainMusicSync/server/logs/Default"
        cp -r "server/logs/Default/"* "dist/BrainMusicSync/server/logs/Default/" 2>/dev/null || true
    fi
    echo "✓ Default logs copied"
fi
echo ""

# Create desktop shortcut for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Creating desktop shortcut..."
    DESKTOP="$HOME/Desktop"
    
    if [ -d "dist/BrainMusicSync.app" ]; then
        # Create alias to .app bundle on desktop
        APP_PATH="$(pwd)/dist/BrainMusicSync.app"
        osascript -e "tell application \"Finder\" to make alias file to POSIX file \"$APP_PATH\" at POSIX file \"$DESKTOP\"" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "✓ Desktop shortcut created"
        else
            echo "⚠ Could not create desktop shortcut automatically"
            echo "  You can manually drag the app to your Desktop or Applications folder"
        fi
    else
        echo "Warning: .app bundle not found, skipping desktop shortcut"
    fi
    echo ""
fi

echo "========================================"
echo "  Build complete!"
echo "========================================"
echo ""

if [[ "$OSTYPE" == "darwin"* ]] && [ -d "dist/BrainMusicSync.app" ]; then
    echo "Application: dist/BrainMusicSync.app"
    echo ""
    echo "To run:"
    echo "  • Double-click: dist/BrainMusicSync.app"
    echo "  • Or drag to Applications folder for permanent installation"
    echo ""
else
    echo "Application: dist/BrainMusicSync/BrainMusicSync"
    echo ""
    echo "To run:"
    echo "  cd dist/BrainMusicSync"
    echo "  ./BrainMusicSync"
    echo ""
    echo "To create desktop shortcut:"
    echo "  Linux: Create .desktop file in ~/.local/share/applications/"
fi
echo ""
read -p "Press Enter to exit..."
