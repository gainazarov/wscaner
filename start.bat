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
echo --- Step 1/5: Checking prerequisites ---
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

echo [i] Redis will run automatically inside Docker (no local install needed)
echo.

:: ═══════════════════════════════════════════════════════════════
:: STEP 2: Clone or update project
:: ═══════════════════════════════════════════════════════════════
echo --- Step 2/5: Project setup ---
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
:: STEP 3: Configure API keys
:: ═══════════════════════════════════════════════════════════════
echo --- Step 3/5: Configuration ---
echo.

set "ENV_FILE=backend\.env"
set "ENV_EXAMPLE=backend\.env.example"

if exist "%ENV_FILE%" (
    :: Check if API keys are already set
    findstr /C:"GOOGLE_SAFE_BROWSING_API_KEY=" "%ENV_FILE%" | findstr /V "GOOGLE_SAFE_BROWSING_API_KEY=$" | findstr /V "GOOGLE_SAFE_BROWSING_API_KEY=your" >nul 2>nul
    if %ERRORLEVEL%==0 (
        echo [OK] API keys already configured
        goto config_done
    )
)

:: Create .env from template if it doesn't exist
if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo [OK] Configuration file created from template
    ) else (
        echo APP_MODE=local> "%ENV_FILE%"
        echo DJANGO_SECRET_KEY=local-dev-key-change-if-needed>> "%ENV_FILE%"
        echo DEBUG=True>> "%ENV_FILE%"
        echo ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*>> "%ENV_FILE%"
        echo CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000>> "%ENV_FILE%"
        echo CELERY_BROKER_URL=redis://redis:6379/0>> "%ENV_FILE%"
        echo CELERY_RESULT_BACKEND=redis://redis:6379/0>> "%ENV_FILE%"
        echo SCANNER_SERVICE_URL=http://scanner:8001>> "%ENV_FILE%"
        echo GOOGLE_SAFE_BROWSING_API_KEY=>> "%ENV_FILE%"
        echo VIRUSTOTAL_API_KEY=>> "%ENV_FILE%"
        echo DOMAIN_REPUTATION_CACHE_HOURS=24>> "%ENV_FILE%"
        echo [OK] Configuration file created
    )
)

echo.
echo [i] Configure API keys for domain reputation checks.
echo     You can skip by pressing Enter (features will be disabled).
echo.

echo   Google Safe Browsing API Key
echo     Get it free: https://developers.google.com/safe-browsing/v4/get-started
set /p "INPUT_GOOGLE=  Enter key (or press Enter to skip): "
if defined INPUT_GOOGLE (
    :: Use PowerShell to safely replace the line in .env
    powershell -Command "(Get-Content '%ENV_FILE%') -replace 'GOOGLE_SAFE_BROWSING_API_KEY=.*', 'GOOGLE_SAFE_BROWSING_API_KEY=%INPUT_GOOGLE%' | Set-Content '%ENV_FILE%'"
    echo [OK] Google Safe Browsing API key saved
) else (
    echo     Skipped — you can add it later in backend\.env
)
echo.

echo   VirusTotal API Key
echo     Get it free: https://www.virustotal.com/gui/my-apikey
set /p "INPUT_VT=  Enter key (or press Enter to skip): "
if defined INPUT_VT (
    powershell -Command "(Get-Content '%ENV_FILE%') -replace 'VIRUSTOTAL_API_KEY=.*', 'VIRUSTOTAL_API_KEY=%INPUT_VT%' | Set-Content '%ENV_FILE%'"
    echo [OK] VirusTotal API key saved
) else (
    echo     Skipped — you can add it later in backend\.env
)

:config_done
echo.

:: ═══════════════════════════════════════════════════════════════
:: STEP 4: Build & Start (with progress)
:: ═══════════════════════════════════════════════════════════════
echo --- Step 4/5: Building ^& starting services ---
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

:: Start containers (includes Redis)
echo [...] Starting containers (including Redis)...
docker compose up -d
echo [OK] All containers started (backend, scanner, frontend, redis, celery)
echo.

:: ═══════════════════════════════════════════════════════════════
:: STEP 5: Health checks & status
:: ═══════════════════════════════════════════════════════════════
echo --- Step 5/5: Waiting for services ---
echo.
echo [...] Waiting for services to be ready...
timeout /t 15 >nul

echo.
echo --- System Status ---
echo.
echo   Redis:    running (Docker)
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo   Scanner:  http://localhost:8001
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
