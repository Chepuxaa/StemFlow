@echo off
cd /d "%~dp0"
"%~dp0StemFlow-worker.exe" --download-model
if errorlevel 1 (
  echo Model setup failed. See the message above.
  pause
  exit /b 1
)
echo Model is ready. Start StemFlow.exe.
pause
