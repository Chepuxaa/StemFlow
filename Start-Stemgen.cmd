@echo off
cd /d "%~dp0"
start "StemFlow" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0stemflow.py"
