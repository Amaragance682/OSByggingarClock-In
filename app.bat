@echo off
cd /d "%~dp0"
REM Optional: Set full path to Python if needed
REM set PYTHON_EXE="C:\Path\To\Python.exe"
echo employee app currently running...

REM Run the app
python -m apps.app %*
pause >nul
