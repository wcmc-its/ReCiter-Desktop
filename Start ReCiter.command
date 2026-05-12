#!/bin/bash
# Start ReCiter Desktop — double-click this from Finder.
#
# Spins up the docker-compose stack on free ports, waits for the backend
# to be healthy, and opens the app in the default browser. No terminal
# experience required after Docker Desktop is installed.

set -u

cd "$(dirname "$0")"

API_PORT=8090   # fixed; frontend bundle bakes this in at build time.

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

# 4. API port is fixed at 8090. Three cases:
#    (a) Free → continue.
#    (b) Held by ReCiter Desktop already (this very compose stack, or a
#        previous one we left behind) → answer "yes, it's us" and just
#        open the browser to the existing instance.
#    (c) Held by something else (often: a developer's native uvicorn
#        running outside docker compose) → friendlier dialog with two
#        choices: stop that process for the user, or cancel.
api_port_holder_pid() {
  lsof -nP -iTCP:"$API_PORT" -sTCP:LISTEN -t 2>/dev/null | head -n1
}

api_port_holder_command() {
  local pid="$1"
  [ -n "$pid" ] || return 0
  ps -p "$pid" -o command= 2>/dev/null || true
}

PORT_HOLDER_PID=$(api_port_holder_pid)
if [ -n "$PORT_HOLDER_PID" ]; then
  HOLDER_CMD=$(api_port_holder_command "$PORT_HOLDER_PID")
  RECITER_COMPOSE_OWNS_8090=0
  # Is it our own running compose stack? docker compose ps emits the api
  # service if and only if the project's stack is up.
  if docker compose ps --services --filter "status=running" 2>/dev/null | grep -qx api; then
    RECITER_COMPOSE_OWNS_8090=1
  fi

  if [ "$RECITER_COMPOSE_OWNS_8090" -eq 1 ]; then
    say "ReCiter Desktop is already running — opening it."
    FRONTEND_PORT=$(docker compose port frontend 3000 2>/dev/null | awk -F: '{print $NF}')
    if [ -n "$FRONTEND_PORT" ]; then
      open "http://localhost:$FRONTEND_PORT"
    fi
    exit 0
  fi

  # Not docker compose — looks like a developer's native uvicorn or
  # another tool. Offer to stop it.
  CHOICE=$(osascript <<EOF 2>/dev/null
display dialog "ReCiter Desktop can't start because another program is using port $API_PORT.

This usually means a leftover ReCiter Desktop process from earlier.

Stop that process and continue?" buttons {"Cancel", "Stop and Continue"} default button "Stop and Continue" with title "ReCiter Desktop" with icon caution
EOF
)
  if echo "$CHOICE" | grep -q "Stop and Continue"; then
    kill "$PORT_HOLDER_PID" 2>/dev/null || true
    # Give it up to 5s to release the port.
    for i in 1 2 3 4 5; do
      sleep 1
      [ -z "$(api_port_holder_pid)" ] && break
    done
    if [ -n "$(api_port_holder_pid)" ]; then
      err "Couldn't free port $API_PORT (PID $PORT_HOLDER_PID still holding it)."
      osa_alert "Couldn't stop the process on port $API_PORT. Restart your computer and try again."
      exit 1
    fi
  else
    exit 0
  fi
fi

# 5. Frontend + DB ports can float.
FRONTEND_PORT=$(find_free_port 3002) || { err "No free frontend port near 3002."; exit 1; }
DB_PORT=$(find_free_port 3306) || { err "No free database port near 3306."; exit 1; }
export FRONTEND_PORT API_PORT DB_PORT

say "Starting ReCiter Desktop"
echo "  Frontend:  http://localhost:$FRONTEND_PORT"
echo "  API:       http://localhost:$API_PORT"
echo "  Database:  localhost:$DB_PORT"

# 6. Bring up the stack. Build on first run pulls images (~150 MB for mariadb).
say "Launching containers (first run downloads ~150 MB)..."
if ! docker compose up -d --quiet-pull; then
  err "docker compose up failed. Check the output above."
  osa_alert "Failed to start the containers. Check Terminal for details."
  exit 1
fi

# 7. Wait for the API. 60s ceiling; the mariadb healthcheck is the slow part.
say "Waiting for the backend to come up..."
for i in $(seq 1 60); do
  if curl -sf "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then
    printf " ready (%ds)\n" "$i"
    break
  fi
  printf "."
  sleep 1
  if [ "$i" -eq 60 ]; then
    err "Backend didn't respond within 60s."
    osa_alert "ReCiter Desktop's backend didn't come up in time.\n\nTry running this script again, or check 'docker compose logs' in Terminal."
    exit 1
  fi
done

# 8. Wait for the frontend separately — Next.js can take a few seconds
#    after the container reports up.
say "Waiting for the frontend..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
    printf " ready (%ds)\n" "$i"
    break
  fi
  printf "."
  sleep 1
done

# 9. Open the browser.
open "http://localhost:$FRONTEND_PORT"

say "ReCiter Desktop is running."
echo "   Open in browser:  http://localhost:$FRONTEND_PORT"
echo "   To stop:          double-click 'Stop ReCiter.command'"
echo ""
echo "This Terminal window can be closed safely; the app stays running."
