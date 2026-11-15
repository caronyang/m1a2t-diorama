@echo off
setlocal
cd /d "%~dp0web"
set PORT=8090
set "PY=python"
where python >nul 2>nul
if errorlevel 1 set "PY=py"
where %PY% >nul 2>nul
if errorlevel 1 (
  echo Python 3 is required to serve the viewer locally.
  echo Install Python or serve this folder with any static web server.
  pause
  exit /b 1
)
start "M1A2T Viewer Server" cmd /k "%PY%" -m http.server %PORT% --bind 127.0.0.1
timeout /t 2 >nul
start "" "http://127.0.0.1:%PORT%/"
echo.
echo M1A2T diorama viewer: http://127.0.0.1:%PORT%/
echo Close the server window to stop.
endlocal
