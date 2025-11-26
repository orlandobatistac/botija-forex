#!/bin/bash
# Deploy script for Kraken AI Trading Bot to VPS

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy.sh <VPS_HOST>"
    exit 1
fi

VPS_HOST=$1
VPS_USER=${VPS_USER:-root}
VPS_PATH="/var/www/kraken-ai-trading-bot"

echo "🚀 Deploying to $VPS_HOST..."

# Push code
echo "📤 Pushing code to repository..."
git push origin main

# SSH and deploy
echo "🔗 Connecting to VPS..."
ssh -u $VPS_USER@$VPS_HOST "cd $VPS_PATH && \
    git pull origin main && \
    source /root/.venv_kraken/bin/activate && \
    pip install -r backend/requirements.txt && \
    sudo systemctl restart kraken-ai-trading-bot.service && \
    sudo systemctl reload nginx && \
    echo '✅ Deployment successful'"

echo "✅ Deploy completed!"
