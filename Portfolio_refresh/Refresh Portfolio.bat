@echo off
title Portfolio Live Refresh
echo ================================================
echo   PORTFOLIO LIVE REFRESH
echo ================================================
echo.

REM ── Check Python is installed ────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found.
    echo.
    echo  Please install Python from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM ── Install required packages if missing ─────────
echo  Checking required packages...
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo  Installing requests...
    pip install requests --quiet
)
python -c "import openpyxl" >nul 2>&1
if errorlevel 1 (
    echo  Installing openpyxl...
    pip install openpyxl --quiet
)

echo  Packages OK.
echo.

REM ── Run the script ───────────────────────────────
python "%~dp0refresh_portfolio.py"

exit /b 0
