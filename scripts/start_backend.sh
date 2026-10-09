#!/bin/bash
echo "============================================"
echo " Campus Intelligence - Backend Server"
echo "============================================"
cd "$(dirname "$0")/../backend"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -f ".env" ]; then
    echo "Generating keys..."
    python -m app.seed.gen_keys
fi

if [ ! -f "campus.db" ]; then
    echo "Seeding database..."
    python -m app.seed.seed_all
fi

echo "Starting backend on port 8000..."
uvicorn app.main:app --reload --port 8000
