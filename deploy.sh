#!/bin/bash
APP_DIR="/home/ec2-user/doanchuyennganh2-be"
VENV_DIR="$APP_DIR/venv"

cd $APP_DIR

echo "🌀 Pulling latest code from GitHub..."
git fetch origin main
git reset --hard origin/main

echo "📦 Activating virtual environment..."
source $VENV_DIR/bin/activate

echo "⬆️ Installing dependencies..."
pip install -r requirements.txt --quiet

echo "🔁 Restarting Gunicorn..."
# Dừng app cũ (nếu có)
pkill gunicorn || true

# Chạy lại app
nohup gunicorn --bind 0.0.0.0:5000 run:app > gunicorn.log 2>&1 &

echo "✅ Deployment complete!"
