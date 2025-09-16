@echo off
title MT5 to Notion Sync

rem Change to script directory
cd /d "%~dp0"

echo ========================================
echo MT5 to Notion Trading Journal Sync
echo ========================================
echo.

rem Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

rem Check if requirements are installed
echo Checking requirements...
python -c "import MetaTrader5, pandas, notion_client, dotenv" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing requirements...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install requirements
        pause
        exit /b 1
    )
)

rem Check if .env file exists
if not exist ".env" (
    echo ERROR: .env file not found
    echo Please create .env file with your configuration
    echo You can copy .env.example and fill in your details
    pause
    exit /b 1
)

echo Starting sync application...
echo.
python notion_sync.py

echo.
echo ========================================
echo Sync completed
echo ========================================
pause