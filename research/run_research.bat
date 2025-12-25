@echo off
:: ============================================
:: Research Pipeline Runner
:: Runs the KNN training and analysis scripts
:: ============================================

title Brain-Music Research Pipeline
cls

echo.
echo ========================================
echo   Brain-Music Research Pipeline
echo ========================================
echo.

:: Navigate to project root (parent of research folder)
cd /d "%~dp0.."

:: Activate Virtual Environment
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo Virtual environment activated.
) else (
    echo Error: Virtual environment '.venv' not found.
    echo Please run 'setup_env.bat' first!
    pause
    exit /b 1
)

:: Install scikit-learn if missing
pip show scikit-learn >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing scikit-learn...
    pip install scikit-learn
)

:: Navigate to research folder
cd research

echo.
echo [1/2] Analyzing session data...
echo.
python analyze_data.py
if %errorlevel% neq 0 (
    echo ERROR: analyze_data.py failed!
    pause
    exit /b 1
)

echo.
echo ----------------------------------------
echo.

echo [2/2] Training KNN model...
echo.
python train_knn.py
if %errorlevel% neq 0 (
    echo ERROR: train_knn.py failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Pipeline Complete!
echo ========================================
echo.
echo Generated files in research/results/:
echo   - plots/bpm_distribution.png
echo   - plots/knn_performance.png
echo   - models/knn_model.joblib
echo.

pause
