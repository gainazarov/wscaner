@echo off
setlocal enabledelayedexpansion
title WScaner - Stop Services

set "PROJECT_DIR=%USERPROFILE%\wscaner"

cls
echo.
echo  =========================================================
echo  =           WScaner - Stop All Services                 =
echo  =========================================================
echo.

if not exist "%PROJECT_DIR%\docker-compose.yml" (
    echo  [!!] Project not found: %PROJECT_DIR%
    echo  Nothing to stop.
    goto :done
)

docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  [!!] Docker not found.
    goto :done
)

docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo  [OK] Docker is not running. Services already stopped.
    goto :done
)

cd /d "%PROJECT_DIR%"

docker compose ps 2>nul | findstr /i "running" >nul 2>&1
if !errorlevel! neq 0 (
    echo  [OK] Services already stopped.
    goto :done
)

echo  Running services:
echo  ---------------------------------------------------------
docker compose ps 2>nul
echo  ---------------------------------------------------------
echo.

echo  [..] Stopping all services...
echo.

docker compose down
if !errorlevel! equ 0 (
    echo.
    echo  [OK] All services stopped.
) else (
    echo.
    echo  [!!] Error. Forcing stop...
    docker compose down --remove-orphans --timeout 10
    echo.
    echo  [OK] Services force-stopped.
)

echo.
echo  ---------------------------------------------------------
echo  Useful commands:
echo    docker compose up -d     - start again
echo    docker system prune -f   - clean Docker cache
echo  ---------------------------------------------------------

:done
echo.
echo  Press any key to exit...
pause >nul
exit /b 0
