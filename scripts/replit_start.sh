#!/usr/bin/env bash
set -eu
exec uv run --no-sync python -m wheat_assistant.cloud
