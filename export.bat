@echo off
cd /d "%~dp0"
REM Optional: Set full path to Python if needed
REM set PYTHON_EXE="C:\Path\To\Python.exe"
echo export executing...

REM Run the app
python -m apps.export_company_reports %*
echo export completed. You can close this window.
pause >nul