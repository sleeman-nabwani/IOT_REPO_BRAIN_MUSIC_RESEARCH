@echo off
:: ======================================================================================
:: BRAIN MUSIC INTERFACE - SETUP WIZARD
:: ======================================================================================
:: This script handles the initial installation. It creates a Python virtual environment,
:: installs all dependencies, and trains the initial KNN model.

title BRAIN MUSIC INTERFACE - SETUP
cls
echo ==================================================
echo       BRAIN MUSIC INTERFACE - SETUP WIZARD
echo ==================================================
echo.
echo This script will:
echo   1. Create a Python Virtual Environment (.venv)
echo   2. Upgrade pip
echo   3. Install all dependencies (pandas, matplotlib, scikit-learn, etc.)
echo   4. Train initial KNN model (if session data exists)
echo.
pause

:: --------------------------
:: Step 1: Create Virtual Environment
:: --------------------------
echo.
echo [1/4] Creating virtual environment...
if not exist .venv (
    python -m venv .venv
    if errorlevel 1 (
        echo Error creating venv! Make sure Python is installed and in your PATH.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists, skipping creation.
)

:: --------------------------
:: Step 2: Activate Environment
:: --------------------------
echo.
echo [2/4] Activating environment and upgrading pip...
call .venv\Scripts\activate.bat
echo Upgrading pip (this can take a few seconds)...
python -m pip install --upgrade pip

:: --------------------------
:: Step 3: Install Dependencies
:: --------------------------
echo.
echo [3/4] Installing dependencies...
echo Showing pip progress so you know it is running...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error installing dependencies!
    pause
    exit /b 1
)
echo Dependencies installed successfully.

:: --------------------------
:: Step 4: Train Initial KNN Model
:: --------------------------
echo.
echo [4/4] Training KNN model...

:: Check if any session data exists
if exist "server\logs\Default" (
    cd research
    python analyze_data.py
    python train_knn.py
    cd ..
) else (
    echo No session data found yet. KNN will train after your first session.
)

:: --------------------------
:: Completion
:: --------------------------
echo.
echo ==================================================
echo       SETUP COMPLETE!
echo ==================================================
echo.
echo You can now use 'start_app.bat' to run the application.
echo.
pause
