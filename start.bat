@echo off
setlocal

title Music Upscaler Pro Studio

cd /d "%~dp0"

echo.
echo ====================================================
echo   Music Upscaler Pro - Studio Server Launcher
echo ====================================================
echo.

:: Activate virtual environment
if exist "%~dp0.venv\Scripts\activate.bat" (
    echo [OK] Activating virtual environment: .venv
    call "%~dp0.venv\Scripts\activate.bat"
) else if exist "%~dp0env\Scripts\activate.bat" (
    echo [OK] Activating virtual environment: env
    call "%~dp0env\Scripts\activate.bat"
) else (
    echo [!] Virtual environment not found, using system Python...
)

:: Check Python availability
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python or set up .venv.
    pause
    exit /b 1
)

echo.
echo Initializing health monitor...
set "STUDIO_HEALTHCHECK_ACTIVE=1"
start "" /b python -m music.healthcheck --open-browser --url http://127.0.0.1:8001/

echo Launching Studio Server...
echo Press Ctrl + C to stop the server.
echo ----------------------------------------------------
echo.

python main.py %*

if errorlevel 1 (
    echo.
    echo [ERROR] Server exited with an error.
    pause
)
