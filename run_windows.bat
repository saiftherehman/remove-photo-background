@echo off
rem Starts Photo Background on Windows. Double-click this file.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 photo_background.py %*
) else (
    python --version >nul 2>nul
    if errorlevel 1 (
        echo Python 3 is not installed.
        echo Download it from https://www.python.org/downloads/windows/
        echo During setup, tick "Add python.exe to PATH".
        pause
        exit /b 1
    )
    python photo_background.py %*
)
if errorlevel 1 pause
