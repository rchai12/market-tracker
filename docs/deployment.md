# Deployment Guide

## Prerequisites

- Two Oracle Cloud free-tier ARM (Ampere A1) VMs provisioned
- Both VMs on the same VCN (Virtual Cloud Network)
- SSH access to both VMs
- A domain name pointed at the Docker VM's public IP (for HTTPS)

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

### 3. Start Services

```bash
docker compose up -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_sp500
```

### 4. Verify

```bash
curl http://localhost/api/health
# Expected: {"status":"healthy","service":"stock-predictor"}
```

### 5. HTTPS (Let's Encrypt)

```bash
# Install certbot
sudo apt install -y certbot

# Get certificate (stop nginx temporarily)
docker compose stop nginx
sudo certbot certonly --standalone -d yourdomain.com

# Copy certs to Docker volume
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /var/lib/docker/volumes/stock-predictor_certbot_certs/_data/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /var/lib/docker/volumes/stock-predictor_certbot_certs/_data/

# Update nginx.conf to use SSL, then restart
docker compose up -d nginx
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
cd ~/stock-predictor
git pull
docker compose build
docker compose up -d
docker compose exec backend alembic upgrade head

# Compute VM
cd /opt/stock-predictor
git pull
cd backend
source .venv/bin/activate
pip install -e ".[worker]"
sudo systemctl restart celery-worker celery-beat
```

## Backup

```bash
# Postgres dump (run on Docker VM)
docker compose exec postgres pg_dump -U sp_user stock_predictor | gzip > backup_$(date +%Y%m%d).sql.gz
```
