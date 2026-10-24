#!/usr/bin/env bash
set -eu
bash scripts/replit_build.sh
exec bash scripts/replit_start.sh
