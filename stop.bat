@echo off
cd /d "%~dp0"
echo Stopping Ziyo Scanner...
docker compose down
echo All services stopped.
pause
