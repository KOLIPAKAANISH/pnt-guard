@echo off
REM run.bat — Start the PNT-Guard engine and signal simulator together.
REM
REM Usage:
REM   run.bat              Start both server and simulator
REM   run.bat --server     Start server only
REM   run.bat --simulator  Start simulator only

setlocal

set MODE=%1
if "%MODE%"=="" set MODE=all

set PORT=%PNT_SERVER_PORT%
if "%PORT%"=="" set PORT=5000

echo Starting PNT-Guard...
echo.

REM Start Flask server in background
echo Starting server on port %PORT%...
start "PNT-Guard Server" python app.py
timeout /t 3 /nobreak >nul

if "%MODE%"=="--server" goto :server_only
if "%MODE%"=="--simulator" goto :simulator_only

REM Start simulator
echo Starting simulator...
start "PNT-Guard Simulator" python signal_simulator.py

goto :running

:server_only
goto :running

:simulator_only
start "PNT-Guard Simulator" python signal_simulator.py
goto :running

:running
echo.
echo ============================================
echo  PNT-Guard is running!
echo.
echo  Dashboard:  http://localhost:%PORT%/dashboard
echo  API Status: http://localhost:%PORT%/status
echo  Fused Pos:  http://localhost:%PORT%/fused
echo  Health:     http://localhost:%PORT%/health
echo ============================================
echo.
echo Close this window or press Ctrl+C to stop.
pause >nul
