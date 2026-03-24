@echo off
chcp 65001 >nul
title Ziyo Scanner — Installer ^& Launcher
cls

echo ═══════════════════════════════════════════════════════════
echo   🚀 Ziyo Scanner — Installer ^& Launcher
echo ═══════════════════════════════════════════════════════════
echo.

set "REPO_URL=https://github.com/gainazarov/wscaner.git"
set "PROJECT_DIR_NAME=wscaner"

:: Save script location
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: ═══════════════════════════════════════════════════════════════
:: STEP 1: Check Prerequisites
:: ═══════════════════════════════════════════════════════════════
echo --- Step 1/4: Checking prerequisites ---
echo.

:: ── 1a. Check Git ──
echo [...] Checking Git...
where git >nul 2>nul
if %ERRORLEVEL%==0 (
    for /f "tokens=3" %%v in ('git --version') do echo [OK] Git found: v%%v
) else (
    echo [!!] Git is not installed.
    echo.
    echo     Please install Git from:
    echo     https://git-scm.com/downloads
    echo.
    echo     After installing, run this script again.
    echo.
    pause
    exit /b 1
)

:: ── 1b. Check Docker ──
echo [...] Checking Docker...
where docker >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [OK] Docker found
) else (
    echo [!!] Docker is not installed.
    echo.
    echo     Please install Docker Desktop from:
    echo     https://www.docker.com/products/docker-desktop/
    echo.
    echo     After installing, run this script again.
    echo.
    pause
    exit /b 1
)

:: ── 1c. Check Docker running ──
echo [...] Checking Docker daemon...
docker info >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [OK] Docker daemon is running
) else (
    echo [!!] Docker daemon is not running.
    echo     Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    echo     Waiting for Docker to start...
    set /a RETRIES=0
    :wait_docker
    timeout /t 3 >nul
    docker info >nul 2>nul
    if %ERRORLEVEL%==0 (
        echo [OK] Docker daemon is running
        goto docker_ok
    )
    set /a RETRIES+=1
    if %RETRIES% GEQ 40 (
        echo [!!] Docker failed to start after 2 minutes.
        echo     Please start Docker Desktop manually and try again.
        pause
        exit /b 1
    )
    goto wait_docker
)
:docker_ok

:: ── 1d. Check Docker Compose ──
echo [...] Checking Docker Compose...
docker compose version >nul 2>nul
if %ERRORLEVEL%==0 (
    echo [OK] Docker Compose found
) else (
    echo [!!] Docker Compose not found. Please update Docker Desktop.
    pause
    exit /b 1
)

echo.

:: ═══════════════════════════════════════════════════════════════
:: STEP 2: Clone or update project
:: ═══════════════════════════════════════════════════════════════
echo --- Step 2/4: Project setup ---
echo.

:: Check if we're inside the project already
if exist "%SCRIPT_DIR%docker-compose.yml" (
    if exist "%SCRIPT_DIR%backend" (
        if exist "%SCRIPT_DIR%scanner" (
            echo [OK] Project found in current directory
            echo [...] Checking for updates...
            git pull --ff-only 2>nul
            if %ERRORLEVEL%==0 (
                echo [OK] Project up to date
            ) else (
                echo [i] Could not auto-update. Continuing with current version.
            )
            goto project_ready
        )
    )
)

:: Not inside project — need to clone
set "PROJECT_DIR=%SCRIPT_DIR%%PROJECT_DIR_NAME%"
if exist "%PROJECT_DIR%\docker-compose.yml" (
    echo [OK] Project already cloned
    echo [...] Pulling latest changes...
    cd /d "%PROJECT_DIR%"
    git pull --ff-only 2>nul
    if %ERRORLEVEL%==0 (
        echo [OK] Project up to date
    ) else (
        echo [i] Could not auto-update. Continuing with current version.
    )
) else (
    echo [...] Cloning project from GitHub...
    echo     %REPO_URL%
    echo.
    git clone --progress "%REPO_URL%" "%PROJECT_DIR%"
    echo.
    echo [OK] Project cloned successfully
    cd /d "%PROJECT_DIR%"
)

:project_ready
echo.

:: ═══════════════════════════════════════════════════════════════
:: STEP 3: Build & Start (with progress)
:: ═══════════════════════════════════════════════════════════════
echo --- Step 3/4: Building ^& starting services ---
echo.
echo [i] Building all images (first run may take 5-10 minutes)...
echo.
echo ---- Docker Build Log ----
echo.

:: Build with plain progress so every step is visible
docker compose build --progress=plain
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!!] Build failed! Check the errors above.
    pause
    exit /b 1
)

echo.
echo ----
echo.
echo [OK] All images built successfully
echo.

:: Start containers
echo [...] Starting containers...
docker compose up -d
echo [OK] Containers started
echo.

:: ═══════════════════════════════════════════════════════════════
:: STEP 4: Health checks & status
:: ═══════════════════════════════════════════════════════════════
echo --- Step 4/4: Waiting for services ---
echo.
echo [...] Waiting for services to be ready...
timeout /t 15 >nul

echo.
echo --- System Status ---
echo.
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo   Scanner:  http://localhost:8001
echo   Redis:    running
echo.
echo ═══════════════════════════════════════════════════════════
echo   🎉 Ziyo Scanner is ready!
echo   Opening: http://localhost:3000
echo ═══════════════════════════════════════════════════════════
echo.

:: ── Open browser ──
start http://localhost:3000

echo To stop: run stop.bat or press any key below
echo.
echo Press any key to stop all services...
pause >nul

echo.
echo [...] Stopping services...
docker compose down
echo [OK] All services stopped. Goodbye!
pause
