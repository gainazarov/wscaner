@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>nul
title Ziyo Scanner - Installer and Launcher
cls

echo ===========================================================
echo   Ziyo Scanner - Installer and Launcher
echo ===========================================================
echo.

set "REPO_URL=https://github.com/gainazarov/wscaner.git"
set "PROJECT_DIR_NAME=wscaner"
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: ===========================================================
:: STEP 1: Check Prerequisites
:: ===========================================================
echo --- Step 1/5: Checking prerequisites ---
echo.

:: -- 1a. Check Git --
echo [...] Checking Git...
where git >nul 2>nul
if errorlevel 1 (
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
echo [OK] Git found

:: -- 1b. Check Docker --
echo [...] Checking Docker...
where docker >nul 2>nul
if errorlevel 1 (
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
echo [OK] Docker found

:: -- 1c. Check Docker running --
echo [...] Checking Docker daemon...
docker info >nul 2>nul
if errorlevel 1 goto start_docker
echo [OK] Docker daemon is running
goto docker_running

:start_docker
echo [!!] Docker daemon is not running.
echo     Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
echo     Waiting for Docker to start (this may take a minute)...
set /a "DC_RETRIES=0"

:wait_docker_loop
timeout /t 3 >nul
docker info >nul 2>nul
if not errorlevel 1 goto docker_started
set /a "DC_RETRIES+=1"
if !DC_RETRIES! GEQ 40 (
    echo [!!] Docker failed to start after 2 minutes.
    echo     Please start Docker Desktop manually and try again.
    pause
    exit /b 1
)
goto wait_docker_loop

:docker_started
echo [OK] Docker daemon is running

:docker_running

:: -- 1d. Check Docker Compose --
echo [...] Checking Docker Compose...
docker compose version >nul 2>nul
if errorlevel 1 (
    echo [!!] Docker Compose not found. Please update Docker Desktop.
    pause
    exit /b 1
)
echo [OK] Docker Compose found
echo [i] Redis will run automatically inside Docker
echo.

:: ===========================================================
:: STEP 2: Clone or update project
:: ===========================================================
echo --- Step 2/5: Project setup ---
echo.

:: Check if we're inside the project already
if not exist "%SCRIPT_DIR%docker-compose.yml" goto not_inside_project
if not exist "%SCRIPT_DIR%backend" goto not_inside_project
if not exist "%SCRIPT_DIR%scanner" goto not_inside_project

:: We are inside the project
echo [OK] Project found in current directory
echo [...] Checking for updates...
git pull --ff-only 2>nul
echo [OK] Project ready
goto project_ready

:not_inside_project
set "PROJECT_DIR=%SCRIPT_DIR%%PROJECT_DIR_NAME%"
if exist "%PROJECT_DIR%\docker-compose.yml" goto update_existing

:: Clone fresh
echo [...] Cloning project from GitHub...
echo     %REPO_URL%
echo.
git clone --progress "%REPO_URL%" "%PROJECT_DIR%"
if errorlevel 1 (
    echo.
    echo [!!] Failed to clone project. Check your internet connection.
    pause
    exit /b 1
)
echo.
echo [OK] Project cloned successfully
cd /d "%PROJECT_DIR%"
goto project_ready

:update_existing
echo [OK] Project already cloned
echo [...] Pulling latest changes...
cd /d "%PROJECT_DIR%"
git pull --ff-only 2>nul
echo [OK] Project ready

:project_ready
echo.

:: ===========================================================
:: STEP 3: Configure API keys
:: ===========================================================
echo --- Step 3/5: Configuration ---
echo.

set "ENV_FILE=backend\.env"
set "ENV_EXAMPLE=backend\.env.example"

:: Check if .env exists and has keys already filled
if not exist "%ENV_FILE%" goto create_env_file

findstr /R "GOOGLE_SAFE_BROWSING_API_KEY=." "%ENV_FILE%" >nul 2>nul
if not errorlevel 1 (
    echo [OK] API keys already configured
    goto config_done
)
goto ask_api_keys

:create_env_file
if exist "%ENV_EXAMPLE%" (
    copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
    echo [OK] Configuration file created from template
) else (
    (
        echo APP_MODE=local
        echo DJANGO_SECRET_KEY=local-dev-key-change-if-needed
        echo DEBUG=True
        echo ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
        echo CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
        echo CELERY_BROKER_URL=redis://redis:6379/0
        echo CELERY_RESULT_BACKEND=redis://redis:6379/0
        echo SCANNER_SERVICE_URL=http://scanner:8001
        echo GOOGLE_SAFE_BROWSING_API_KEY=
        echo VIRUSTOTAL_API_KEY=
        echo DOMAIN_REPUTATION_CACHE_HOURS=24
    ) > "%ENV_FILE%"
    echo [OK] Configuration file created
)

:ask_api_keys
echo.
echo [i] Configure API keys for domain reputation checks.
echo     You can skip by pressing Enter (features will be disabled).
echo.
echo   Google Safe Browsing API Key
echo     Get free: https://developers.google.com/safe-browsing/v4/get-started

set "INPUT_GOOGLE="
set /p "INPUT_GOOGLE=  Enter key (or Enter to skip): "

if not defined INPUT_GOOGLE (
    echo     Skipped
) else (
    powershell -Command "(Get-Content '!ENV_FILE!') -replace 'GOOGLE_SAFE_BROWSING_API_KEY=.*', 'GOOGLE_SAFE_BROWSING_API_KEY=!INPUT_GOOGLE!' | Set-Content '!ENV_FILE!'" 2>nul
    echo [OK] Google Safe Browsing key saved
)

echo.
echo   VirusTotal API Key
echo     Get free: https://www.virustotal.com/gui/my-apikey

set "INPUT_VT="
set /p "INPUT_VT=  Enter key (or Enter to skip): "

if not defined INPUT_VT (
    echo     Skipped
) else (
    powershell -Command "(Get-Content '!ENV_FILE!') -replace 'VIRUSTOTAL_API_KEY=.*', 'VIRUSTOTAL_API_KEY=!INPUT_VT!' | Set-Content '!ENV_FILE!'" 2>nul
    echo [OK] VirusTotal key saved
)

:config_done
echo.

:: ===========================================================
:: STEP 4: Build and Start (with progress)
:: ===========================================================
echo --- Step 4/5: Building and starting services ---
echo.

:: -- Check for port conflicts --
echo [...] Checking for port conflicts...
set "PORT_CONFLICT=0"
for %%P in (8000 8001 3000 6080) do (
    netstat -ano 2>nul | findstr ":%%P " | findstr "LISTENING" >nul 2>nul
    if not errorlevel 1 (
        echo [!!] Port %%P is already in use
        set "PORT_CONFLICT=1"
    )
)
if "!PORT_CONFLICT!"=="1" (
    echo.
    echo [i] Some ports are busy. Docker may fail to start.
    echo     Close applications using these ports and try again,
    echo     or press any key to continue anyway.
    pause >nul
) else (
    echo [OK] No port conflicts
)
echo.

echo [i] Building all images (first run may take 5-10 minutes)...
echo.
echo ---- Docker Build Log ----
echo.

docker compose build --progress=plain
if errorlevel 1 (
    echo.
    echo [!!] Build failed! Check the errors above.
    echo.
    pause
    exit /b 1
)

echo.
echo ----
echo [OK] All images built successfully
echo.

echo [...] Starting containers (Redis, Backend, Scanner, Frontend)...
docker compose up -d
if errorlevel 1 (
    echo.
    echo [!!] Failed to start containers.
    echo.
    pause
    exit /b 1
)
echo [OK] All containers started
echo.

:: ===========================================================
:: STEP 5: Health checks
:: ===========================================================
echo --- Step 5/5: Waiting for services ---
echo.
echo [...] Waiting for services to be ready (15 seconds)...
timeout /t 15 >nul

echo.
echo --- System Status ---
echo.
echo   Redis:    running (Docker container)
echo   Backend:  http://localhost:8000
echo   Scanner:  http://localhost:8001
echo   Frontend: http://localhost:3000
echo.
echo ===========================================================
echo   Ziyo Scanner is ready!
echo   Opening browser: http://localhost:3000
echo ===========================================================
echo.

start "" "http://localhost:3000"

echo To stop: run stop.bat or press any key below
echo.
echo Press any key to stop all services...
pause >nul

echo.
echo [...] Stopping services...
docker compose down
echo [OK] All services stopped. Goodbye!
echo.
pause
