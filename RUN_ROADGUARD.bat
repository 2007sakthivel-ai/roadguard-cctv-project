@echo off
setlocal
cd /d "%~dp0"

curl.exe --fail --silent http://127.0.0.1:8000/api/health >nul 2>&1
if not errorlevel 1 goto open_dashboard

if not exist ".venv\Scripts\python.exe" (
    echo Setting up RoadGuard. This can take a few minutes.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
    if errorlevel 1 (
        echo.
        echo Setup failed. Read the error above and check README.md.
        pause
        exit /b 1
    )
)

echo Starting RoadGuard...
start "RoadGuard Server" powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -File "%~dp0start.ps1"

for /l %%i in (1,1,60) do (
    curl.exe --fail --silent http://127.0.0.1:8000/api/health >nul 2>&1
    if not errorlevel 1 goto open_dashboard
    timeout /t 1 /nobreak >nul
)

echo RoadGuard did not become ready within 60 seconds.
echo Check the RoadGuard Server window for startup errors.
pause
exit /b 1

:open_dashboard
start "" "http://127.0.0.1:8000"
echo RoadGuard is ready. In the dashboard, select a camera or video and click Start monitoring.
echo Keep the RoadGuard Server window open. Press Ctrl+C in that window to stop the server.
exit /b 0
