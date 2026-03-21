#!/bin/bash
set -e

# Quick setup script for CBSE Marksheet Fetcher

echo "Setting up CBSE Marksheet Fetcher..."

# Detect Python version
PYTHON_CMD=""
if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "Error: Python 3.11+ not found. Please install Python 3.11 or later."
    exit 1
fi

echo "Using Python: $PYTHON_CMD"

# Setup Backend
echo "Setting up backend..."
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    echo "Created virtual environment"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Create .env from example if not exists
if [ ! -f ".env" ]; then
    cp ../.env.example .env
    echo "Created .env file. Please add your OPENAI_API_KEY to backend/.env"
fi

cd ..

# Setup Frontend
echo "Setting up frontend..."
cd frontend

# Install dependencies
npm install

cd ..

echo ""
echo "Setup complete!"
echo ""
echo "To start the application:"
echo ""
echo "  1. Add your OPENAI_API_KEY to backend/.env"
echo "  2. Start backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  3. Start frontend: cd frontend && npm run dev"
echo "  4. Open http://localhost:3000"
echo ""
echo "To run tests:"
echo "  cd backend && source venv/bin/activate && pytest tests/ -v"
