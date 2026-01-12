@echo off
:: ======================================================================================
:: BRAIN MUSIC INTERFACE - LAUNCHER SCRIPT
:: ======================================================================================
:: This script is the entry point for the user. It ensures the application runs
:: inside the correct Python Virtual Environment (.venv) to avoid missing libraries.

:: Navigate to project root (three levels up from setup/Windows/dev/)
cd /d "%~dp0..\..\..\"

title BRAIN MUSIC INTERFACE
cls

:: 1. Header Display
echo ==================================================
echo       STARTING BRAIN MUSIC INTERFACE...
echo ==================================================
echo.

:: 2. Check for Virtual Environment
:: We look for the 'activate.bat' script. If it exists, we run it to switch 
:: python versions to the one in '.venv'.
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    :: Error Handler: If the user hasn't run setup_env.bat yet
    echo Error: Virtual environment '.venv' not found.
    echo Please run 'setup_env.bat' first!
    pause
    exit /b
)

:: 3. Launch Application
:: Now that venv is active, 'python' refers to the isolated version with all libraries.
echo Launching GUI...
python server\gui_app.py

:: 4. Exit Handling
:: 'errorlevel' checks the exit code of the previous command (python).
:: If python crashed (code != 0), we pause so the user can see the error message.
:: If python exited cleanly (code 0, e.g. clicking Quit), we close the window immediately.
if errorlevel 1 (
    echo.
    echo Application crashed or exited with error.
    pause
)
