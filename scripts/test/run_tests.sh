#!/usr/bin/env bash
set -euo pipefail

# Run pytest using Python 3.12 explicitly (avoids accidentally picking up a pytest
# installed for a different Python like macOS system Python 3.9).
if [[ -x "/opt/homebrew/bin/python3.12" ]]; then
  PY="/opt/homebrew/bin/python3.12"
elif command -v python3.12 >/dev/null 2>&1; then
  PY="$(command -v python3.12)"
else
  echo "ERROR: python3.12 not found. Install Python 3.12 or update this script." >&2
  exit 1
fi

# Headless-friendly defaults for pygame tests.
# These env vars only apply to this command (won't affect running the game).
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-dummy}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-dummy}"
export PYGAME_HIDE_SUPPORT_PROMPT="${PYGAME_HIDE_SUPPORT_PROMPT:-1}"

exec "$PY" -m pytest "$@"
