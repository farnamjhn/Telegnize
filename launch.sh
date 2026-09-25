#!/usr/bin/env bash
#
# Telegnize Launcher: Starts both FastAPI backend and Vite frontend
# Usage: ./launch.sh [--no-open]
#

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

BACKEND_PORT=8000
FRONTEND_PORT=3000
BACKEND_PID=""
FRONTEND_PID=""

# Color helpers
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

cleanup() {
    echo -e "\n${YELLOW}Shutting down Telegnize services...${NC}"
    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    echo -e "${GREEN}All services stopped cleanly.${NC}"
    exit 0
}

free_port() {
    local port=$1
    local name=$2
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo -e "${YELLOW}Port $port is currently in use by PID(s): $pids ($name). Freeing port...${NC}"
        for pid in $pids; do
            kill "$pid" 2>/dev/null || true
        done
        sleep 1
    fi
}

trap cleanup SIGINT SIGTERM EXIT

echo -e "${BOLD}${BLUE}=======================================${NC}"
echo -e "${BOLD}${BLUE}          Starting Telegnize           ${NC}"
echo -e "${BOLD}${BLUE}=======================================${NC}"

# Check for uv
if ! command -v uv &>/dev/null; then
    echo -e "${RED}Error: 'uv' is not installed. Install it from https://docs.astral.sh/uv/${NC}"
    exit 1
fi

# Check for node and npm
if ! command -v npm &>/dev/null; then
    echo -e "${RED}Error: 'npm' is not installed. Node.js is required for the frontend.${NC}"
    exit 1
fi

# Check frontend node_modules
if [[ ! -d "frontend/node_modules" ]]; then
    echo -e "${YELLOW}Installing frontend dependencies (npm install)...${NC}"
    npm --prefix frontend install
fi

# Ensure ports are free
free_port "$BACKEND_PORT" "backend"
free_port "$FRONTEND_PORT" "frontend"

# 1. Start Backend
echo -e "${BLUE}--> Starting backend (FastAPI on http://127.0.0.1:${BACKEND_PORT})...${NC}"
uv run python main.py &
BACKEND_PID=$!

# Wait for backend to be ready
echo -n "    Waiting for backend to be responsive..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:${BACKEND_PORT}/docs" >/dev/null 2>&1; then
        echo -e " ${GREEN}Ready!${NC}"
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "\n${RED}Backend process died unexpectedly. Check logs above.${NC}"
        exit 1
    fi
    sleep 0.5
    echo -n "."
done

# 2. Start Frontend
echo -e "${BLUE}--> Starting frontend (Vite on http://localhost:${FRONTEND_PORT})...${NC}"
npm --prefix frontend run dev &
FRONTEND_PID=$!

echo -e "\n${BOLD}${GREEN}Telegnize is up and running!${NC}"
echo -e "  ${BOLD}Web UI:${NC}    ${GREEN}http://localhost:${FRONTEND_PORT}${NC}"
echo -e "  ${BOLD}API Docs:${NC}  ${BLUE}http://127.0.0.1:${BACKEND_PORT}/docs${NC}"
echo -e "  ${BOLD}Model:${NC}     ${YELLOW}$( [ -d "checkpoints/laya-multilingual-telegnize" ] && echo "checkpoints/laya-multilingual-telegnize (Fine-tuned)" || echo "Stock Laya" )${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop both backend and frontend.${NC}\n"

# Optionally open browser if on macOS and not disabled
if [[ "${1:-}" != "--no-open" ]] && command -v open &>/dev/null; then
    sleep 1
    open "http://localhost:${FRONTEND_PORT}" 2>/dev/null || true
fi

# Wait for background processes
wait
