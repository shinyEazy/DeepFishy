#!/bin/bash
echo "Starting DeepFishy..."

cd src/deepfishy

uv run langgraph dev --allow-blocking --no-browser
