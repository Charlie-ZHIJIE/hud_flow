#!/bin/bash
# API keys expected in environment
cd "$(dirname "$0")"
uv run hud eval local-hud.json claude \
  --model claude-sonnet-4-5-20250929 \
  --max-steps 50 \
  --group-size 5 \
  --yes --verbose
