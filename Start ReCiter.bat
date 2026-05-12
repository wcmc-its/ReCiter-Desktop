@echo off
REM Start ReCiter Desktop — double-click this from File Explorer.
REM
REM Spins up the docker-compose stack, waits for the backend to be
REM healthy, and opens the app in the default browser. No PowerShell
REM or command-prompt experience needed after Docker Desktop is
REM installed.

setlocal enabledelayedexpansion

REM cd to the script's directory so docker compose finds the yml.
cd /d "%~dp0"

set API_PORT=8090

REM 1. Docker installed?
where docker >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [X] Docker Desktop is not installed.
  echo.
  echo  Opening the download page...
  start "" "https://www.docker.com/products/docker-desktop"
  pause
  exit /b 1
)

REM 2. Docker daemon running?
docker info >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [X] Docker Desktop is installed but not running.
  echo.
  echo  Please open Docker Desktop, wait for it to start, then run this
  echo  script again.
  pause
  exit /b 1
)

REM 3. API port is fixed at 8090. Three cases handled below:
REM    (a) Free → continue.
REM    (b) Held by our running docker compose stack → just open the
REM        browser to the existing instance.
REM    (c) Held by something else → offer to stop it (typically a
REM        developer's leftover uvicorn).
netstat -an | findstr /R /C:":%API_PORT% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  REM Is it our compose stack?
  for /f "tokens=*" %%S in ('docker compose ps --services --filter status^=running 2^>nul') do (
    if "%%S"=="api" set COMPOSE_API_RUNNING=1
  )
  if defined COMPOSE_API_RUNNING (
    echo  ReCiter Desktop is already running - opening it.
    for /f "tokens=2 delims=:" %%P in ('docker compose port frontend 3000 2^>nul') do set EXISTING_FRONTEND_PORT=%%P
    if defined EXISTING_FRONTEND_PORT start "" "http://localhost:!EXISTING_FRONTEND_PORT!"
    timeout /t 3 >nul
    exit /b 0
  )

  REM Not us. Ask before killing.
  choice /C YN /N /M "Port %API_PORT% is held by another process (probably a leftover ReCiter backend). Stop it and continue? [Y/N] "
  if errorlevel 2 exit /b 0

  REM Find the PID on 8090 and kill it.
  for /f "tokens=5" %%P in ('netstat -aon ^| findstr /R /C:":%API_PORT% .*LISTENING"') do (
    taskkill /PID %%P /F >nul 2>&1
  )
  timeout /t 3 >nul

  REM Verify it's free.
  netstat -an | findstr /R /C:":%API_PORT% .*LISTENING" >nul 2>&1
  if not errorlevel 1 (
    echo  [X] Couldn't free port %API_PORT%. Restart your computer and try again.
    pause
    exit /b 1
  )
)

REM 4. Frontend + DB ports can float.
set FRONTEND_PORT=
for /L %%P in (3002,1,3022) do (
  if not defined FRONTEND_PORT (
    netstat -an | findstr /R /C:":%%P .*LISTENING" >nul 2>&1
    if errorlevel 1 set FRONTEND_PORT=%%P
  )
)
if not defined FRONTEND_PORT (
  echo  [X] No free frontend port between 3002 and 3022.
  pause
  exit /b 1
)

set DB_PORT=
for /L %%P in (3306,1,3326) do (
  if not defined DB_PORT (
    netstat -an | findstr /R /C:":%%P .*LISTENING" >nul 2>&1
    if errorlevel 1 set DB_PORT=%%P
  )
)
if not defined DB_PORT (
  echo  [X] No free database port between 3306 and 3326.
  pause
  exit /b 1
)

echo.
echo  Starting ReCiter Desktop
echo    Frontend:  http://localhost:%FRONTEND_PORT%
echo    API:       http://localhost:%API_PORT%
echo    Database:  localhost:%DB_PORT%
echo.

echo  Launching containers (first run downloads ~150 MB)...
docker compose up -d --quiet-pull
if errorlevel 1 (
  echo.
  echo  [X] docker compose up failed. Check the output above.
  pause
  exit /b 1
)

echo  Waiting for the backend...
set BACKEND_READY=
for /L %%I in (1,1,60) do (
  if not defined BACKEND_READY (
    curl -sf "http://localhost:%API_PORT%/api/health" >nul 2>&1
    if not errorlevel 1 (
      set BACKEND_READY=1
      echo    ready ^(%%Is^).
    ) else (
      timeout /t 1 /nobreak >nul
    )
  )
)
if not defined BACKEND_READY (
  echo  [X] Backend did not respond within 60 seconds.
  echo      Try running 'docker compose logs' to see what failed.
  pause
  exit /b 1
)

echo  Waiting for the frontend...
for /L %%I in (1,1,30) do (
  curl -sf "http://localhost:%FRONTEND_PORT%" >nul 2>&1
  if not errorlevel 1 goto :frontend_ready
  timeout /t 1 /nobreak >nul
)
:frontend_ready

start "" "http://localhost:%FRONTEND_PORT%"

echo.
echo  ReCiter Desktop is running.
echo    Open in browser:  http://localhost:%FRONTEND_PORT%
echo    To stop:          double-click 'Stop ReCiter.bat'
echo.
echo  This window can be closed.
timeout /t 5 >nul
endlocal
