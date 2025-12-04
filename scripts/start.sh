#!/bin/bash
echo "Starting DeepFishy..."

cd ..
cd src/app/engine
uv run langgraph dev --allow-blocking --no-browser
