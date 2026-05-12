#!/bin/bash
# Start ReCiter Desktop — double-click this from Finder.
#
# Spins up the docker-compose stack on free ports, waits for the backend
# to be healthy, and opens the app in the default browser. No terminal
# experience required after Docker Desktop is installed.

set -u

cd "$(dirname "$0")"

say() { printf "\n\033[1;36m▸\033[0m %s\n" "$*"; }
err() { printf "\n\033[1;31m✗\033[0m %s\n" "$*" >&2; }
osa_alert() { osascript -e "display dialog \"$1\" buttons {\"OK\"} default button \"OK\" with icon note with title \"ReCiter Desktop\"" >/dev/null 2>&1 || true; }

# 1. Docker Desktop installed?
if ! command -v docker >/dev/null 2>&1; then
  err "Docker Desktop is not installed."
  osa_alert "Docker Desktop is required to run ReCiter Desktop.\n\nClick OK to open the download page."
  open "https://www.docker.com/products/docker-desktop"
  exit 1
fi

# 2. Docker daemon running?
if ! docker info >/dev/null 2>&1; then
  err "Docker Desktop is installed but not running."
  osa_alert "Please start Docker Desktop, wait until it finishes loading, then run this script again."
  open -a Docker >/dev/null 2>&1 || true
  exit 1
fi

# 3. Free-port finder. Looks for a TCP listener on the given port; if
#    something's there, walks up to +20 looking for a free slot. Bails
#    if it can't find one.
find_free_port() {
  local start=$1
  local p=$start
  local limit=$((start + 20))
  while [ $p -lt $limit ]; do
    if ! lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "$p"
      return 0
    fi
    p=$((p + 1))
  done
  return 1
}

# 4. If our compose stack is already running, just open the browser.
if docker compose ps --services --filter "status=running" 2>/dev/null | grep -qx frontend; then
  EXISTING_FRONTEND_PORT=$(docker compose port frontend 3000 2>/dev/null | awk -F: '{print $NF}')
  if [ -n "$EXISTING_FRONTEND_PORT" ]; then
    say "ReCiter Desktop is already running — opening it."
    open "http://localhost:$EXISTING_FRONTEND_PORT"
    exit 0
  fi
fi

# 5. Pick free host ports for the frontend and DB. The API is not
#    exposed to the host — the frontend proxies /api/* to it over the
#    docker network — so no API port collisions are possible.
FRONTEND_PORT=$(find_free_port 3002) || { err "No free frontend port near 3002."; exit 1; }
DB_PORT=$(find_free_port 3306) || { err "No free database port near 3306."; exit 1; }
export FRONTEND_PORT DB_PORT

say "Starting ReCiter Desktop"
echo "  Frontend:  http://localhost:$FRONTEND_PORT"
echo "  Database:  localhost:$DB_PORT"

# 6. Bring up the stack. --build picks up any local source changes; the
#    docker layer cache makes no-op runs fast (~1s) when nothing changed.
#    First run downloads ~150 MB for the mariadb base image.
say "Launching containers (first run downloads ~150 MB)..."
if ! docker compose up -d --build --quiet-pull; then
  err "docker compose up failed. Check the output above."
  osa_alert "Failed to start the containers. Check Terminal for details."
  exit 1
fi

# 7. Single readiness check via the frontend's proxy. /api/health going
#    through localhost:$FRONTEND_PORT confirms the frontend is serving
#    AND the proxy is wired AND the backend is healthy — covers the
#    whole chain in one curl.
say "Waiting for ReCiter Desktop to come up..."
for i in $(seq 1 90); do
  if curl -sf "http://localhost:$FRONTEND_PORT/api/health" >/dev/null 2>&1; then
    printf " ready (%ds)\n" "$i"
    break
  fi
  printf "."
  sleep 1
  if [ "$i" -eq 90 ]; then
    err "ReCiter Desktop didn't come up in 90s."
    osa_alert "ReCiter Desktop didn't come up in time.\n\nTry running this script again, or check 'docker compose logs' in Terminal."
    exit 1
  fi
done

# 8. Open the browser.
open "http://localhost:$FRONTEND_PORT"

say "ReCiter Desktop is running."
echo "   Open in browser:  http://localhost:$FRONTEND_PORT"
echo "   To stop:          double-click 'Stop ReCiter.command'"
echo ""
echo "This Terminal window can be closed safely; the app stays running."
