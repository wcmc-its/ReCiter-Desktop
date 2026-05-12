@echo off
REM Stop ReCiter Desktop — double-click this from File Explorer.

cd /d "%~dp0"

where docker >nul 2>&1
if errorlevel 1 (
  echo  Docker is not installed — nothing to stop.
  pause
  exit /b 0
)

docker info >nul 2>&1
if errorlevel 1 (
  echo  Docker Desktop is not running — the containers are already down.
  pause
  exit /b 0
)

echo  Stopping ReCiter Desktop...
docker compose down

echo.
echo  Stopped. Data is preserved in Docker's volume — restart anytime.
timeout /t 5 >nul
