#!/bin/bash
# Start development environment for Kraken AI Trading Bot

set -e

echo "🚀 Starting Kraken AI Trading Bot development environment..."

# Check if virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "📦 Creating virtual environment..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    cd ..
else
    source backend/venv/bin/activate
fi

echo "✅ Virtual environment ready"
echo ""
echo "📡 Starting FastAPI server on http://localhost:8001"
echo "📊 Dashboard available at http://localhost:8001/frontend/"
echo "📚 API Docs at http://localhost:8001/docs"
echo ""

cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
