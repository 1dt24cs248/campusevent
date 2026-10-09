#!/bin/bash
echo "============================================"
echo " Campus Intelligence - Frontend Server"
echo "============================================"
cd "$(dirname "$0")/../frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

echo "Starting frontend on port 5173..."
npm run dev
