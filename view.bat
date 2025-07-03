@echo off
cd /d "%~dp0"
echo Running admin_view...
python -m apps.admin_view
echo.
echo Press any key to exit...
pause >nul
