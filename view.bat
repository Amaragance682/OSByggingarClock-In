@echo off
cd /d "%~dp0"
REM Optional: Set full path to Python if needed
REM set PYTHON_EXE="C:\Path\To\Python.exe"
echo admin_view currently running...

REM Run the app
start /min python -m apps.admin_view %*
pause >nul