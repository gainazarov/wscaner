@echo off
chcp 65001 >nul
title Ziyo Scanner — Local Launcher
cls

echo ═══════════════════════════════════════════════════════
echo   🚀 Ziyo Scanner — Local-First Launcher
echo ═══════════════════════════════════════════════════════
echo.

:: Navigate to script directory
cd /d "%~dp0"

:: ── 1. Check Git ──
echo [..] Checking Git...
where git >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [OK] Git found
) else (
    echo [!!] Git not found. Please install Git.
    echo     https://git-scm.com/downloads
    pause
    exit /b 1
)

:: ── 2. Check Docker ──
echo [..] Checking Docker...
where docker >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [OK] Docker found
) else (
    echo [!!] Docker not found. Please install Docker Desktop.
    echo     https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

:: ── 3. Check Docker running ──
echo [..] Checking Docker daemon...
docker info >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [OK] Docker is running
) else (
    echo [!!] Docker is not running. Please start Docker Desktop.
    echo     Waiting for Docker...
    :wait_docker
    timeout /t 3 >nul
    docker info >nul 2>nul
    if %ERRORLEVEL% NEQ 0 goto wait_docker
    echo [OK] Docker is running
)

:: ── 4. Check Docker Compose ──
echo [..] Checking Docker Compose...
docker compose version >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [OK] Docker Compose found
) else (
    echo [!!] Docker Compose not found. Please update Docker Desktop.
    pause
    exit /b 1
)

echo.
echo --- Starting services ---
echo.

:: ── 5. Build and start ──
echo [..] Building and starting containers (first run may take a few minutes)...
docker compose up -d --build

echo.
echo [..] Waiting for services to be ready...
timeout /t 10 >nul

echo.
echo --- System Status ---
echo.
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo   Scanner:  http://localhost:8001
echo.
echo ═══════════════════════════════════════════════════════
echo   Ziyo Scanner is ready!
echo   Opening: http://localhost:3000
echo ═══════════════════════════════════════════════════════
echo.

:: ── 6. Open browser ──
start http://localhost:3000

echo Press any key to stop all services...
pause >nul

echo.
echo [..] Stopping services...
docker compose down
echo [OK] All services stopped.
pause
