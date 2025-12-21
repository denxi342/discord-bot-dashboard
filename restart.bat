    @echo off
echo Stopping old processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM py.exe /T 2>nul
timeout /t 2 >nul

echo Starting Web Dashboard...
start "Web Dashboard" cmd /k "py web.py"

echo Starting Discord Bot...
start "Discord Bot" cmd /k "py main.py"

echo Done! Bot and Dashboard are running in new windows.
timeout /t 5
