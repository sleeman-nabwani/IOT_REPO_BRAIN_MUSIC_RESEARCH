@echo off
:: ============================================
:: LightGBM Research Pipeline Runner
:: Runs the LightGBM analysis and training scripts
:: Optional flags:
::   --optimize              Run tune_lgbm.py (grid search) instead of train_lgbm.py
::   --head TARGET [SUFFIX]  Train a user head after model training (TARGET=user name or path)
:: ============================================

title Brain-Music LightGBM Research Pipeline
cls

set OPTIMIZE=0
set HEAD_TARGET=
set HEAD_SUFFIX=

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--optimize" (
    set OPTIMIZE=1
    shift
    goto parse_args
)
if /I "%~1"=="--head" (
    shift
    if "%~1"=="" goto args_done
    set HEAD_TARGET=%~1
    shift
    if not "%~1"=="" (
        set HEAD_SUFFIX=%~1
        shift
    )
    goto parse_args
)
shift
goto parse_args
:args_done

echo.
echo ========================================
echo   Brain-Music LightGBM Research Pipeline
echo ========================================
echo.
set SCRIPT_DIR=%~dp0
set REPO_DIR=%SCRIPT_DIR%

:: If the script sits in research\LightGBM, jump two levels up; otherwise assume we're already at repo root.
if exist "%SCRIPT_DIR%run_lgbm.bat" (
    set REPO_DIR=%SCRIPT_DIR%..\..
) else if exist "%SCRIPT_DIR%research\LightGBM\run_lgbm.bat" (
    set REPO_DIR=%SCRIPT_DIR%
)

echo [DEBUG] Batch location: %SCRIPT_DIR%
echo [DEBUG] Batch name: %0
echo [DEBUG] Before cd, working directory: %cd%
echo [DEBUG] Repo dir resolved to: %REPO_DIR%
echo [DEBUG] Checking for venv activate at "%cd%\.venv\Scripts\activate.bat"

:: Navigate to project root
cd /d "%REPO_DIR%"

echo [DEBUG] After cd, working directory: %cd%
echo [DEBUG] Checking for venv activate at "%cd%\.venv\Scripts\activate.bat"

:: Activate Virtual Environment
if defined VIRTUAL_ENV (
    echo [DEBUG] VIRTUAL_ENV already set: %VIRTUAL_ENV%
) else if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo Virtual environment activated.
) else (
    echo Error: Virtual environment '.venv' not found at "%cd%\.venv"
    echo Please run 'setup_env.bat' first!
    pause
    exit /b 1
)

:: Ensure dependencies
pip show lightgbm >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing LightGBM...
    pip install lightgbm
)

pip show scikit-learn >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing scikit-learn...
    pip install scikit-learn
)

:: Navigate to LightGBM research folder
cd research\LightGBM

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

echo [2/2] Training LightGBM model...
echo.
echo [DEBUG] OPTIMIZE value: "%OPTIMIZE%"
set TRAIN_ERR=0
if "%OPTIMIZE%"=="1" goto run_opt

python train_lgbm.py
set TRAIN_ERR=%errorlevel%
goto after_train

:run_opt
echo Using optimizer (tune_lgbm.py)...
if exist tune_lgbm.py (
    python tune_lgbm.py
    set TRAIN_ERR=%errorlevel%
) else (
    echo ERROR: tune_lgbm.py not found in %cd%
    pause
    exit /b 1
)

:after_train
if %TRAIN_ERR% neq 0 (
    echo ERROR: model training failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   LightGBM Pipeline Complete!
echo ========================================
echo.
echo Generated files in research\LightGBM\results\:
echo   - plots\lgbm_bpm_distribution.png
echo   - plots\lgbm_performance.png
echo   - models\lgbm_model.joblib
echo.

if not "%HEAD_TARGET%"=="" (
    echo [User Head] Training calibration head for %HEAD_TARGET% ...
    if "%HEAD_SUFFIX%"=="" (
        call run_lgbm_user_head.bat "%HEAD_TARGET%"
    ) else (
        call run_lgbm_user_head.bat "%HEAD_TARGET%" "%HEAD_SUFFIX%"
    )
)

echo.
echo ========================================
echo   Pipeline Complete!
echo ========================================
echo.

pause

