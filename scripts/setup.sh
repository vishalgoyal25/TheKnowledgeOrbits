#!/bin/bash
# setup.sh - Environment Setup Script for TheKnowledgeOrbits

echo "Starting environment setup..."

# 1. Backend Setup
echo "Creating backend virtual environment..."
cd backend
python -m venv venv
source venv/bin/activate || source venv/Scripts/activate
pip install -r requirements.txt
echo "Backend dependencies installed."

# 2. Database Initialization
echo "Running migrations..."
python manage.py migrate
echo "Database ready."

# 3. Frontend Setup
echo "Installing frontend dependencies..."
cd ../frontend
npm install
echo "Frontend ready."

echo "Setup complete! Use 'just dev' to start the project."
