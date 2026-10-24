#!/usr/bin/env bash
set -eu
uv sync --frozen --extra replit --no-dev
npm --prefix frontend ci
npm --prefix frontend run build
