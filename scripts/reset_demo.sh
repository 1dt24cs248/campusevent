#!/bin/bash
echo "============================================"
echo " Campus Intelligence - Reset Demo Data"
echo "============================================"
cd "$(dirname "$0")/../backend"

source .venv/bin/activate

echo "Deleting campus.db..."
rm -f campus.db

echo "Re-seeding database..."
python -m app.seed.seed_all

echo "Done! Restart the backend server."
