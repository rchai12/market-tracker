#!/bin/bash
set -e

echo "=== Setting up Stock Predictor Compute VM ==="

# 1. Install system dependencies
echo "Installing system dependencies..."
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3.11-dev git

# 2. Clone repo and create virtualenv
echo "Setting up project..."
sudo mkdir -p /opt/stock-predictor
sudo chown $(whoami):$(whoami) /opt/stock-predictor
git clone <REPO_URL> /opt/stock-predictor
cd /opt/stock-predictor/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[worker]"

# 3. Pre-download FinBERT model
echo "Downloading FinBERT model (this may take a few minutes)..."
python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; \
           AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert'); \
           AutoTokenizer.from_pretrained('ProsusAI/finbert')"

# 4. Setup environment
echo "Setting up environment..."
cp /opt/stock-predictor/deploy/compute-vm/.env.compute.example /opt/stock-predictor/backend/.env
echo ">>> IMPORTANT: Edit /opt/stock-predictor/backend/.env with your actual values <<<"

# 5. Install systemd units
echo "Installing systemd services..."
sudo cp /opt/stock-predictor/deploy/compute-vm/celery-worker.service /etc/systemd/system/
sudo cp /opt/stock-predictor/deploy/compute-vm/celery-beat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable celery-worker celery-beat

echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Edit /opt/stock-predictor/backend/.env with your actual values"
echo "  2. sudo systemctl start celery-worker celery-beat"
echo "  3. sudo systemctl status celery-worker celery-beat"
