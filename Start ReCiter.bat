@echo off
REM Start ReCiter Desktop — double-click this from File Explorer.
REM
REM Spins up the docker-compose stack, waits for the app to be
REM reachable, and opens it in the default browser. No command-prompt
REM experience needed after Docker Desktop is installed.

setlocal enabledelayedexpansion

REM cd to the script's directory so docker compose finds the yml.
cd /d "%~dp0"

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

REM 3. If our compose stack is already running, just open the browser.
set COMPOSE_FRONTEND_RUNNING=
for /f "tokens=*" %%S in ('docker compose ps --services --filter status^=running 2^>nul') do (
  if "%%S"=="frontend" set COMPOSE_FRONTEND_RUNNING=1
)
if defined COMPOSE_FRONTEND_RUNNING (
  echo  ReCiter Desktop is already running - opening it.
  for /f "tokens=2 delims=:" %%P in ('docker compose port frontend 3000 2^>nul') do set EXISTING_FRONTEND_PORT=%%P
  if defined EXISTING_FRONTEND_PORT start "" "http://localhost:!EXISTING_FRONTEND_PORT!"
  timeout /t 3 >nul
  exit /b 0
)

REM 4. Pick free host ports for the frontend and DB. The API is not
REM    exposed to the host — the frontend proxies /api/* to it over the
REM    docker network — so no API port collisions are possible.
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
echo    Database:  localhost:%DB_PORT%
echo.

echo  Launching containers (first run downloads ~150 MB)...
docker compose up -d --build --quiet-pull
if errorlevel 1 (
  echo.
  echo  [X] docker compose up failed. Check the output above.
  pause
  exit /b 1
)

REM Single readiness check via the frontend's proxy. /api/health going
REM through localhost:FRONTEND_PORT covers frontend + proxy + backend.
echo  Waiting for ReCiter Desktop to come up...
set READY=
for /L %%I in (1,1,90) do (
  if not defined READY (
    curl -sf "http://localhost:%FRONTEND_PORT%/api/health" >nul 2>&1
    if not errorlevel 1 (
      set READY=1
      echo    ready ^(%%Is^).
    ) else (
      timeout /t 1 /nobreak >nul
    )
  )
)
if not defined READY (
  echo  [X] ReCiter Desktop did not come up within 90 seconds.
  echo      Run 'docker compose logs' to see what failed.
  pause
  exit /b 1
)

start "" "http://localhost:%FRONTEND_PORT%"

echo.
echo  ReCiter Desktop is running.
echo    Open in browser:  http://localhost:%FRONTEND_PORT%
echo    To stop:          double-click 'Stop ReCiter.bat'
echo.
echo  This window can be closed.
timeout /t 5 >nul
endlocal
