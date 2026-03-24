@echo off
setlocal enabledelayedexpansion
title WScaner - Setup and Launch

set "REPO_URL=https://github.com/gainazarov/wscaner.git"
set "PROJECT_DIR=%USERPROFILE%\wscaner"
set "FRONTEND_URL=http://localhost:3000"

cls
echo.
echo  =========================================================
echo  =                                                       =
echo  =           WScaner - Setup and Launch                  =
echo  =        Link Discovery and Security Scanner            =
echo  =                                                       =
echo  =========================================================
echo.

if exist "%PROJECT_DIR%\docker-compose.yml" (
    set "MODE=update"
    echo  [MODE] Update and launch
) else (
    set "MODE=install"
    echo  [MODE] First install
)
echo.

:: === STEP 1: Git ===
echo  ---------------------------------------------------------
echo  [1/8] Checking Git...
echo  ---------------------------------------------------------

git --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=3" %%v in ('git --version 2^>nul') do set "GIT_VER=%%v"
    echo  [OK] Git found: v!GIT_VER!
) else (
    echo  [!!] Git not found
    echo.
    winget --version >nul 2>&1
    if !errorlevel! equ 0 (
        echo  [..] Installing Git via winget...
        winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
        set "PATH=!PATH!;C:\Program Files\Git\cmd;C:\Program Files\Git\bin"
        git --version >nul 2>&1
        if !errorlevel! equ 0 (
            echo  [OK] Git installed
        ) else (
            echo  [!!] Git installed but terminal restart required.
            echo  Close this window and run start.bat again.
            goto :fail
        )
    ) else (
        echo  [!!] Please install Git manually:
        echo  https://git-scm.com/downloads
        start "" "https://git-scm.com/downloads"
        echo  Then run start.bat again.
        goto :fail
    )
)
echo.

:: === STEP 2: Docker ===
echo  ---------------------------------------------------------
echo  [2/8] Checking Docker...
echo  ---------------------------------------------------------

docker --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=3" %%v in ('docker --version 2^>nul') do (
        set "DV=%%v"
        set "DV=!DV:,=!"
    )
    echo  [OK] Docker found: v!DV!
) else (
    echo  [!!] Docker not found
    echo  Please install Docker Desktop:
    echo  https://www.docker.com/products/docker-desktop/
    start "" "https://www.docker.com/products/docker-desktop/"
    echo  Then run start.bat again.
    goto :fail
)

docker compose version >nul 2>&1
if !errorlevel! neq 0 (
    echo  [!!] Docker Compose not found. Update Docker Desktop.
    goto :fail
)
echo  [OK] Docker Compose found
echo.

:: === STEP 3: Docker running ===
echo  ---------------------------------------------------------
echo  [3/8] Checking Docker Engine...
echo  ---------------------------------------------------------

docker info >nul 2>&1
if !errorlevel! equ 0 (
    echo  [OK] Docker is running
    goto :docker_ok
)

echo  [..] Docker not running, starting Docker Desktop...
set "DS=0"
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    set "DS=1"
)
if !DS! equ 0 (
    echo  [!!] Cannot find Docker Desktop.
    echo  Start Docker Desktop manually and run start.bat again.
    goto :fail
)

echo  [..] Waiting for Docker Engine (up to 2 min)...
set "DR=0"
for /L %%i in (1,1,60) do (
    if !DR! equ 0 (
        docker info >nul 2>&1
        if !errorlevel! equ 0 (
            set "DR=1"
        ) else (
            timeout /t 2 /nobreak >nul 2>&1
        )
    )
)
if !DR! equ 0 (
    echo  [!!] Docker did not start in 2 minutes.
    echo  Start Docker Desktop manually and try again.
    goto :fail
)
echo  [OK] Docker is ready

:docker_ok
echo.

:: === STEP 4-5: Clone/Update + .env ===
if "!MODE!"=="install" (
    call :do_install
) else (
    call :do_update
)
if !errorlevel! neq 0 goto :fail

:: === STEP 6: Build ===
echo  ---------------------------------------------------------
echo  [6/8] Building containers...
echo  ---------------------------------------------------------
echo  This may take 3-10 minutes on first build...
echo.

cd /d "%PROJECT_DIR%"
docker compose build
if !errorlevel! neq 0 (
    echo  [!!] Build failed. Check Docker and try again.
    goto :fail
)
echo.
echo  [OK] Build complete
echo.

:: === STEP 7: Start ===
echo  ---------------------------------------------------------
echo  [7/8] Starting services...
echo  ---------------------------------------------------------

cd /d "%PROJECT_DIR%"
docker compose up -d
if !errorlevel! neq 0 (
    echo  [!!] Failed to start services.
    goto :fail
)
echo.
echo  [..] Waiting for services to be ready...

set "RDY=0"
for /L %%i in (1,1,20) do (
    if !RDY! equ 0 (
        timeout /t 3 /nobreak >nul 2>&1
        docker compose ps 2>nul | findstr /i "running" >nul 2>&1
        if !errorlevel! equ 0 set "RDY=1"
    )
)

if !RDY! equ 1 (
    echo  [OK] All services are running
) else (
    echo  [..] Services are still starting, wait 20-30 sec...
)
echo.

:: === STEP 8: Open browser ===
echo  ---------------------------------------------------------
echo  [8/8] Opening browser...
echo  ---------------------------------------------------------

timeout /t 3 /nobreak >nul 2>&1
start "" "%FRONTEND_URL%"
echo  [OK] Browser opened: %FRONTEND_URL%
echo.

:: === DONE ===
echo.
echo  =========================================================
echo  =                                                       =
echo  =           [OK] WScaner is running!                    =
echo  =                                                       =
echo  =    WEB:  http://localhost:3000                         =
echo  =    API:  http://localhost:8000/api                     =
echo  =                                                       =
echo  =========================================================
echo.
echo  To stop: run stop.bat or press any key here
echo.
pause >nul

echo.
echo  [..] Stopping services...
cd /d "%PROJECT_DIR%"
docker compose down
echo  [OK] Services stopped. Goodbye!
echo.
timeout /t 3 /nobreak >nul 2>&1
exit /b 0

:: =============================================================
:: INSTALL subroutine
:: =============================================================
:do_install
echo  ---------------------------------------------------------
echo  [4/8] Cloning project...
echo  ---------------------------------------------------------

git clone "%REPO_URL%" "%PROJECT_DIR%"
if !errorlevel! neq 0 (
    echo  [!!] Clone failed. Check internet connection.
    exit /b 1
)
echo  [OK] Repository cloned
echo.

cd /d "%PROJECT_DIR%"

echo  ---------------------------------------------------------
echo  [5/8] Setting up environment...
echo  ---------------------------------------------------------
echo.
echo  API keys are needed for domain reputation features.
echo  You can leave them empty - scanner will work without them.
echo.

set "GSB_KEY="
set "VT_KEY="
set /p "GSB_KEY=  GOOGLE_SAFE_BROWSING_API_KEY (Enter to skip): "
set /p "VT_KEY=  VIRUSTOTAL_API_KEY (Enter to skip): "

set "SK=wscaner-%RANDOM%%RANDOM%%RANDOM%%RANDOM%"

> "%PROJECT_DIR%\backend\.env" (
    echo # WScaner Backend Environment
    echo APP_MODE=local
    echo DJANGO_SECRET_KEY=!SK!
    echo DEBUG=True
    echo ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
    echo CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    echo CELERY_BROKER_URL=redis://redis:6379/0
    echo CELERY_RESULT_BACKEND=redis://redis:6379/0
    echo SCANNER_SERVICE_URL=http://scanner:8001
    echo GOOGLE_SAFE_BROWSING_API_KEY=!GSB_KEY!
    echo VIRUSTOTAL_API_KEY=!VT_KEY!
    echo DOMAIN_REPUTATION_CACHE_HOURS=24
)

echo.
echo  [OK] .env file created
echo.
exit /b 0

:: =============================================================
:: UPDATE subroutine
:: =============================================================
:do_update
echo  ---------------------------------------------------------
echo  [4/8] Updating project...
echo  ---------------------------------------------------------

cd /d "%PROJECT_DIR%"

echo  [..] Stopping current containers...
docker compose down >nul 2>&1

echo  [..] Pulling latest changes...
git pull origin main
if !errorlevel! neq 0 (
    echo  [!!] Update failed.
    exit /b 1
)
echo  [OK] Project updated
echo.

echo  ---------------------------------------------------------
echo  [5/8] Checking .env...
echo  ---------------------------------------------------------

if exist "%PROJECT_DIR%\backend\.env" (
    echo  [OK] .env file found, settings preserved
) else (
    echo  [!!] .env file missing, creating new one...
    echo.

    set "GSB_KEY="
    set "VT_KEY="
    set /p "GSB_KEY=  GOOGLE_SAFE_BROWSING_API_KEY (Enter to skip): "
    set /p "VT_KEY=  VIRUSTOTAL_API_KEY (Enter to skip): "

    set "SK=wscaner-%RANDOM%%RANDOM%%RANDOM%%RANDOM%"

    > "%PROJECT_DIR%\backend\.env" (
        echo # WScaner Backend Environment
        echo APP_MODE=local
        echo DJANGO_SECRET_KEY=!SK!
        echo DEBUG=True
        echo ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
        echo CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
        echo CELERY_BROKER_URL=redis://redis:6379/0
        echo CELERY_RESULT_BACKEND=redis://redis:6379/0
        echo SCANNER_SERVICE_URL=http://scanner:8001
        echo GOOGLE_SAFE_BROWSING_API_KEY=!GSB_KEY!
        echo VIRUSTOTAL_API_KEY=!VT_KEY!
        echo DOMAIN_REPUTATION_CACHE_HOURS=24
    )

    echo  [OK] .env file created
)
echo.
exit /b 0

:: =============================================================
:: FAIL label - keeps window open
:: =============================================================
:fail
echo.
echo  Press any key to exit...
pause >nul
exit /b 1
