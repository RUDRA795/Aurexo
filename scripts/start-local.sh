#!/usr/bin/env bash
set -euo pipefail

docker compose up -d
cd "$(dirname "$0")/../backend"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest
python run.py
