@echo off
setlocal EnableDelayedExpansion

:: Navigate to project root (two levels up from setup/Windows/)
cd /d "%~dp0..\.."

:: Parse command line arguments
if /I "%~1"=="--clean" goto :clean_only
if /I "%~1"=="-c" goto :clean_only

echo ========================================
echo   Brain Music Sync - Build System
echo   Building Portable Application
echo ========================================
echo.

:: Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo [Step 1/5] Python found
python --version
echo.

:: Check/create virtual environment
echo [Step 2/5] Setting up virtual environment...
if not exist .venv\Scripts\activate.bat (
    echo Creating new virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
echo.

:: Install/upgrade dependencies
echo [Step 3/5] Installing dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo Dependencies installed successfully
echo.

:: Clean previous builds
echo [Step 4/5] Cleaning previous builds...

:: Kill any running instances of the application
taskkill /F /IM BrainMusicSync.exe >nul 2>&1
timeout /t 1 /nobreak >nul

if exist build (
    rmdir /s /q build 2>nul
    if exist build (
        echo Warning: Could not fully clean build\ folder. Some files may be in use.
    )
)

if exist dist (
    rmdir /s /q dist 2>nul
    if exist dist (
        echo Warning: Could not fully clean dist\ folder. Some files may be in use.
        echo Please close any running instances of BrainMusicSync and try again.
        pause
        exit /b 1
    )
)
echo.

:: Build with PyInstaller
echo [Step 5/5] Building executable...
echo This may take 3-5 minutes...
echo.
pyinstaller --clean setup/build.spec
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
    echo Check the output above for errors.
    pause
    exit /b 1
)
echo.
echo Executable built successfully!
echo.

:: Copy MIDI files
echo Copying MIDI files to portable version...
if exist midi_files (
    xcopy /E /I /Y "midi_files\*.mid" "dist\BrainMusicSync\midi_files\" >nul
    echo MIDI files copied
)
echo.

:: Copy Default logs
echo Copying Default logs to portable version...
if exist "server\logs\Default" (
    xcopy /E /I /Y "server\logs\Default" "dist\BrainMusicSync\server\logs\Default\" >nul
    echo Default logs copied
)
echo.

echo ========================================
echo   Build complete!
echo ========================================
echo.
echo Executable: dist\BrainMusicSync\BrainMusicSync.exe
echo.

:: Ask about desktop shortcut
cd /d "%~dp0..\.."
echo.
echo ========================================
echo.
set /p "CREATE_SHORTCUT=Create desktop shortcut? (Y/N): "
if /I "%CREATE_SHORTCUT%"=="Y" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$WScriptShell = New-Object -ComObject WScript.Shell; $desktopPath = [Environment]::GetFolderPath('Desktop'); $Shortcut = $WScriptShell.CreateShortcut(\"$desktopPath\Brain Music Sync.lnk\"); $Shortcut.TargetPath = (Resolve-Path 'dist\BrainMusicSync\BrainMusicSync.exe').Path; $Shortcut.WorkingDirectory = (Resolve-Path 'dist\BrainMusicSync').Path; $Shortcut.Save(); Write-Host 'Desktop shortcut created successfully!' -ForegroundColor Green"
) else (
    echo Skipping desktop shortcut creation.
)

echo.
echo Launching application...
start "" "dist\BrainMusicSync\BrainMusicSync.exe"
echo.
pause
exit /b 0

:clean_only
:: Clean build artifacts
echo ========================================
echo   Cleaning Build Artifacts
echo ========================================
echo.

:: Kill any running instances of the application
echo Closing any running BrainMusicSync instances...
taskkill /F /IM BrainMusicSync.exe >nul 2>&1
timeout /t 1 /nobreak >nul

if exist build (
    rmdir /s /q build 2>nul
    if exist build (
        echo Warning: Could not fully remove build\
    ) else (
        echo Removed: build\
    )
)

if exist dist (
    rmdir /s /q dist 2>nul
    if exist dist (
        echo Error: Could not remove dist\ - files may be in use
        echo Please close any running instances of BrainMusicSync
        pause
        exit /b 1
    ) else (
        echo Removed: dist\
    )
)

:: Clean Python cache
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    rmdir /s /q "%%d"
    echo Removed: %%d
)

:: Clean .pyc files
del /s /q *.pyc 2>nul

:: Remove desktop shortcut if it exists
echo.
echo Checking for desktop shortcut...
powershell -Command "$desktop = [Environment]::GetFolderPath('Desktop'); $shortcut = Join-Path $desktop 'Brain Music Sync.lnk'; if (Test-Path $shortcut) { Remove-Item $shortcut -Force; Write-Host 'Removed: Brain Music Sync.lnk from Desktop' -ForegroundColor Green } else { Write-Host 'No desktop shortcut found' -ForegroundColor Yellow }"

echo.
echo ========================================
echo   Clean complete!
echo ========================================
echo.
pause
exit /b 0

