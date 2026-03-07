# Deployment Guide

## Prerequisites

- Two Oracle Cloud free-tier ARM (Ampere A1) VMs provisioned
- Both VMs on the same VCN (Virtual Cloud Network)
- SSH access to both VMs
- A domain name with Cloudflare DNS proxied to the Docker VM's public IP
- An existing shared nginx reverse proxy on the Docker VM (routes by domain)

## Docker VM Setup

### 1. Install Docker

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect
```

### 2. Clone and Configure

```bash
git clone <REPO_URL> ~/stock-predictor
cd ~/stock-predictor

# Create .env from template
cp deploy/docker-vm/.env.docker.example .env
```

Edit `.env` with real values:
```bash
# Generate a secure secret key:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
# Generate a secure password:
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

### 3. Create shared Docker network

The `proxy_net` network connects stock-predictor to the existing shared nginx proxy on the VM.

```bash
docker network create proxy_net
```

### 4. Start Services

```bash
docker compose up -d
docker compose exec backend alembic upgrade head

# Seed tickers (6 sectors, ~86 tickers, 20 sub-industries) + full historical market data (~30+ years)
make seed-all
# Or step by step:
# make seed          # Seed 6 sectors (~86 tickers) with industry classifications
# make seed-history  # Backfill full OHLCV history (takes a few minutes)
```

### 5. Verify

```bash
# Direct check (via internal nginx)
docker compose exec nginx curl -f http://localhost/api/health
# Expected: {"status":"healthy","service":"stock-predictor"}
```

### 6. Connect to Shared Reverse Proxy

The existing nginx proxy on the Docker VM routes traffic by domain. Cloudflare handles SSL.

**Add `proxy_net` to the existing app's docker-compose** (the one running the shared nginx):
```yaml
networks:
  proxy_net:
    external: true
```

Connect the shared nginx service to `proxy_net`:
```yaml
services:
  nginx:  # the existing shared nginx
    networks:
      - default
      - proxy_net
```

**Uncomment the stock predictor server block** in the existing app's `nginx/conf.d/default.conf`:
```nginx
server {
    listen 80;
    server_name stocks.yourdomain.com;

    location / {
        proxy_pass http://stock-predictor-nginx:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Restart the existing nginx, then add a Cloudflare DNS A record for `stocks.yourdomain.com` → Docker VM public IP (proxied).

### 7. Verify end-to-end

```bash
curl https://stocks.yourdomain.com/api/health
# Expected: {"status":"healthy","service":"stock-predictor"}
```

## Compute VM Setup

### 1. Run Setup Script

```bash
# Copy the repo or just the setup script to the compute VM
scp -r stock-predictor/ compute-vm:~/

# SSH in and run setup
ssh compute-vm
chmod +x ~/stock-predictor/scripts/setup_compute_vm.sh
~/stock-predictor/scripts/setup_compute_vm.sh
```

### 2. Configure Environment

```bash
nano /opt/stock-predictor/backend/.env
```

Set `DATABASE_URL` and `REDIS_URL` to point to the Docker VM's **internal IP**:
```
DATABASE_URL=postgresql+asyncpg://sp_user:YOUR_PASSWORD@10.0.0.X:5432/stock_predictor
REDIS_URL=redis://:YOUR_PASSWORD@10.0.0.X:6379/0
```

### 3. Start Workers

```bash
sudo systemctl start celery-worker celery-beat
sudo systemctl status celery-worker celery-beat
```

### 4. Verify Workers

```bash
# Check logs
sudo journalctl -u celery-worker -f
sudo journalctl -u celery-beat -f
```

## Oracle Cloud Network Configuration

### Security List Rules (Docker VM)

| Direction | Protocol | Port | Source | Purpose |
|-----------|----------|------|--------|---------|
| Ingress | TCP | 80 | 0.0.0.0/0 | HTTP |
| Ingress | TCP | 443 | 0.0.0.0/0 | HTTPS |
| Ingress | TCP | 5432 | 10.0.0.0/24 | Postgres (VCN only) |
| Ingress | TCP | 6379 | 10.0.0.0/24 | Redis (VCN only) |
| Ingress | TCP | 22 | your-ip/32 | SSH |

### Security List Rules (Compute VM)

| Direction | Protocol | Port | Source | Purpose |
|-----------|----------|------|--------|---------|
| Ingress | TCP | 22 | your-ip/32 | SSH |
| Egress | TCP | 5432 | 10.0.0.0/24 | Postgres |
| Egress | TCP | 6379 | 10.0.0.0/24 | Redis |
| Egress | TCP | 443 | 0.0.0.0/0 | HTTPS (scraping) |

## Postgres Configuration

For the free tier, expose Postgres on the internal network by editing `docker-compose.yml`:

```yaml
  postgres:
    # Add this to expose on internal network
    ports:
      - "10.0.0.X:5432:5432"  # Replace with Docker VM's internal IP
```

Similarly for Redis:
```yaml
  redis:
    ports:
      - "10.0.0.X:6379:6379"
```

## Monitoring

### Health Check

```bash
bash scripts/healthcheck.sh
```

### Logs

```bash
# Docker VM
docker compose logs -f backend
docker compose logs -f postgres

# Compute VM
sudo journalctl -u celery-worker -f --no-pager
sudo journalctl -u celery-beat -f --no-pager
```

### Disk Usage

```bash
# Check Postgres data size
docker compose exec postgres psql -U sp_user -d stock_predictor -c "SELECT pg_size_pretty(pg_database_size('stock_predictor'));"
```

## Updating

```bash
# Docker VM
cd ~/market-tracker
git pull
docker compose up -d --build frontend backend   # Only rebuild changed services
docker compose exec backend alembic upgrade head  # If migrations changed

# Compute VM
cd /opt/stock-predictor
git pull
cd backend
source .venv/bin/activate
pip install -e ".[worker]"                        # If dependencies changed
sudo cp ../deploy/compute-vm/celery-worker.service /etc/systemd/system/  # If service file changed
sudo systemctl daemon-reload
sudo systemctl restart celery-worker celery-beat
```

### Manual Task Triggers (Compute VM)

```bash
cd /opt/stock-predictor/backend

# Trigger scraping
.venv/bin/celery -A worker.celery_app call worker.tasks.scraping.orchestrate_scraping --queue scraping

# Trigger sentiment analysis
.venv/bin/celery -A worker.celery_app call worker.tasks.sentiment.sentiment_task.process_new_articles_sentiment --queue sentiment

# Trigger signal generation
.venv/bin/celery -A worker.celery_app call worker.tasks.signals.signal_generator.generate_all_signals --queue signals
```

## Backup

```bash
# Postgres dump (run on Docker VM)
docker compose exec postgres pg_dump -U sp_user stock_predictor | gzip > backup_$(date +%Y%m%d).sql.gz
```
