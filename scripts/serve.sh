#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-3500}"
exec waitress-serve --listen="0.0.0.0:${PORT}" ytanalyzer.webapp.app:create_app

