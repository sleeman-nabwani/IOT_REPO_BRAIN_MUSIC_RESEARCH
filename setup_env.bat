@echo off
:: ======================================================================================
:: BRAIN MUSIC INTERFACE - SETUP WIZARD
:: ======================================================================================
:: This script handles the initial installation. It creates a secluded "box" (virtual environment)
:: for Python and puts all the required libraries (pandas, matplotlib, etc.) inside it.

title BRAIN MUSIC INTERFACE - SETUP
cls
echo ==================================================
echo       BRAIN MUSIC INTERFACE - SETUP WIZARD
echo ==================================================
echo.
echo This script will:
echo 1. Create a Python Virtual Environment (venv311)
echo 2. Upgrade pip
echo 3. Install necessary libraries (pandas, matplotlib, pyserial)
echo.
pause

:: Step 1: Create Virtual Environment
:: 'python -m venv venv311' tells Python to make a new folder 'venv311' with its own copy of Python.
echo.
echo [1/3] Creating virtual environment...
python -m venv venv311
if errorlevel 1 (
    echo Error creating venv! Make sure Python is installed and in your PATH.
    pause
    exit /b
)

:: Step 2: Activate Environment
:: We must activate it so that the following 'pip install' commands affect 
:: THIS environment, not the global computer settings.
echo.
echo [2/3] Activating environment and upgrading pip...
call venv311\Scripts\activate.bat
python -m pip install --upgrade pip

:: Step 3: Install Dependencies
:: Reads the list of libraries from 'requirements.txt' and downloads them.
echo.
echo [3/3] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Error installing dependencies!
    pause
    exit /b
)

:: Completion
echo.
echo ==================================================
echo       SETUP COMPLETE!
echo ==================================================
echo.
echo You can now use 'start_app.bat' to run the application.
echo.
pause
