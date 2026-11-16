@echo off
rem Double-click this file to start the StockVision dashboard on this laptop.
rem Keep the window open while you use the dashboard; close it to stop.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The Python environment is missing. Run this once in PowerShell:  .\tasks.ps1 install
    pause
    exit /b 1
)
echo Starting StockVision. Your browser will open at http://localhost:8501
echo Keep this window open. Close it to stop the dashboard.
echo.
".venv\Scripts\python.exe" -m streamlit run app/dashboard.py
echo.
echo The dashboard has stopped.
pause
