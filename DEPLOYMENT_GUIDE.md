# Kaison K1 - Deployment Guide

Complete deployment instructions for production environments: cloud, on-premises, and hybrid.

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Cloud Deployment (GCP)](#cloud-deployment-gcp)
3. [Docker Container Deployment](#docker-container-deployment)
4. [On-Premises Deployment](#on-premises-deployment)
5. [Production Configuration](#production-configuration)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Scaling](#scaling)

---

## Pre-Deployment Checklist

Before deploying to production:

- [ ] All environment variables configured (see [Production Configuration](#production-configuration))
- [ ] Database initialized and tested
- [ ] SSL/TLS certificates obtained
- [ ] Firewall rules configured
- [ ] Backup strategy implemented
- [ ] Monitoring and alerting configured
- [ ] Security scan completed
- [ ] Load balancer configured (if needed)
- [ ] DNS records updated
- [ ] Team trained on system

---

## Cloud Deployment (GCP)

### Quick Cloud Deployment (Recommended)

**Prerequisites:**
- GCP account with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed locally

### Step 1: Prepare GCP Project

```bash
# Set your GCP project
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"

gcloud config set project $GCP_PROJECT_ID
gcloud config set compute/region $GCP_REGION

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  compute.googleapis.com \
  cloudkms.googleapis.com \
  secretmanager.googleapis.com \
  container.googleapis.com
```

### Step 2: Setup Secret Manager

```bash
# Store sensitive configuration in Google Secret Manager

# Anthropic API Key
echo -n "sk-ant-your-key" | gcloud secrets create anthropic-api-key --data-file=-

# Database password
echo -n "your-secure-password" | gcloud secrets create db-password --data-file=-

# Other secrets as needed
gcloud secrets create openai-api-key --data-file=-
gcloud secrets create gemini-api-key --data-file=-
```

### Step 3: Setup Cloud SQL (PostgreSQL)

```bash
# Create Cloud SQL instance
gcloud sql instances create k1-db \
  --database-version=POSTGRES_15 \
  --tier=db-custom-2-8192 \
  --region=$GCP_REGION \
  --availability-type=REGIONAL \
  --enable-bin-log \
  --backup-start-time=02:00

# Create database
gcloud sql databases create k1 --instance=k1-db

# Create service account for application
gcloud iam service-accounts create k1-app \
  --display-name="K1 Application Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member=serviceAccount:k1-app@$GCP_PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

### Step 4: Build & Push Docker Image

```bash
# Build Docker image
docker build -t gcr.io/$GCP_PROJECT_ID/k1-backend:latest apps/backend/
docker build -t gcr.io/$GCP_PROJECT_ID/k1-frontend:latest apps/frontend/

# Push to Container Registry
docker push gcr.io/$GCP_PROJECT_ID/k1-backend:latest
docker push gcr.io/$GCP_PROJECT_ID/k1-frontend:latest
```

### Step 5: Deploy to Cloud Run

```bash
# Backend Service
gcloud run deploy k1-backend \
  --image gcr.io/$GCP_PROJECT_ID/k1-backend:latest \
  --platform managed \
  --region $GCP_REGION \
  --memory 2Gi \
  --cpu 1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=postgresql://user:pass@cloudsql-host/k1 \
  --update-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest

# Frontend Service
gcloud run deploy k1-frontend \
  --image gcr.io/$GCP_PROJECT_ID/k1-frontend:latest \
  --platform managed \
  --region $GCP_REGION \
  --memory 512Mi \
  --cpu 0.5 \
  --allow-unauthenticated
```

### Step 6: Setup Cloud Load Balancer

```bash
# Create backend service
gcloud compute backend-services create k1-backend-service \
  --global \
  --protocol=HTTPS \
  --port-name=https \
  --health-checks=k1-health-check

# Create URL map
gcloud compute url-maps create k1-lb \
  --default-service=k1-backend-service

# Create HTTPS proxy with SSL cert
gcloud compute target-https-proxies create k1-https-proxy \
  --url-map=k1-lb \
  --ssl-certificates=your-cert

# Create forwarding rule
gcloud compute forwarding-rules create k1-lb-https \
  --global \
  --target-https-proxy=k1-https-proxy \
  --address=your-static-ip \
  --ports=443
```

---

## Docker Container Deployment

### Build Docker Images

**Backend Dockerfile** (`apps/backend/Dockerfile`):

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY apps/backend/ .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile** (`apps/frontend/Dockerfile`):

```dockerfile
FROM node:18-alpine as builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Build and Run Locally

```bash
# Build images
docker build -t k1-backend:latest apps/backend/
docker build -t k1-frontend:latest apps/frontend/

# Run with docker-compose
docker-compose up -d
```

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: k1
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build:
      context: .
      dockerfile: apps/backend/Dockerfile
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@postgres:5432/k1
      REDIS_URL: redis://redis:6379
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      DEBUG_MODE: "false"
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  frontend:
    build:
      context: .
      dockerfile: apps/frontend/Dockerfile
    ports:
      - "3000:80"
    environment:
      REACT_APP_API_URL: http://backend:8000

volumes:
  postgres_data:
```

---

## On-Premises Deployment

### System Requirements

**Server Hardware:**
- CPU: 8+ cores
- RAM: 16GB+ (32GB recommended)
- Storage: 500GB+ SSD
- OS: Ubuntu 20.04 LTS or Rocky Linux 8+

### Step 1: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
  python3.11 \
  python3.11-venv \
  python3.11-dev \
  postgresql-15 \
  postgresql-contrib-15 \
  redis-server \
  nodejs \
  npm \
  nginx \
  certbot \
  python3-certbot-nginx \
  git

# Install Docker (optional but recommended)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

### Step 2: Setup Database

```bash
# Create PostgreSQL database and user
sudo -u postgres psql << EOF
CREATE DATABASE k1;
CREATE USER k1_user WITH PASSWORD 'secure_password_here';
ALTER ROLE k1_user SET client_encoding TO 'utf8';
ALTER ROLE k1_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE k1_user SET default_transaction_deferrable TO on;
ALTER ROLE k1_user SET default_transaction_read_committed TO on;
GRANT ALL PRIVILEGES ON DATABASE k1 TO k1_user;
EOF

# Verify connection
psql -U k1_user -d k1 -h localhost -c "SELECT version();"
```

### Step 3: Deploy Application

```bash
# Clone repository
git clone https://github.com/kaison-ai/kaison-k1.git
cd Kaison_Latest_Build

# Create system user for application
sudo useradd -r -s /bin/bash -d /opt/k1 k1

# Setup directory structure
sudo mkdir -p /opt/k1 /var/log/k1 /var/lib/k1
sudo chown -R k1:k1 /opt/k1 /var/log/k1 /var/lib/k1

# Install backend
cd apps/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend
cd ../frontend
npm install
npm run build
```

### Step 4: Configure Systemd Services

**Backend Service** (`/etc/systemd/system/k1-backend.service`):

```ini
[Unit]
Description=Kaison K1 Backend API
After=postgresql.service redis-server.service network.target
Wants=postgresql.service redis-server.service

[Service]
Type=notify
User=k1
Group=k1
WorkingDirectory=/opt/k1/apps/backend
Environment="DATABASE_URL=postgresql://k1_user:password@localhost/k1"
Environment="ANTHROPIC_API_KEY=your-key"
Environment="DEBUG_MODE=false"
ExecStart=/opt/k1/apps/backend/venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Frontend Service** (`/etc/systemd/system/k1-frontend.service`):

```ini
[Unit]
Description=Kaison K1 Frontend
After=k1-backend.service network.target

[Service]
Type=simple
User=k1
Group=k1
WorkingDirectory=/opt/k1/apps/frontend
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port 3000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable k1-backend k1-frontend
sudo systemctl start k1-backend k1-frontend
sudo systemctl status k1-backend k1-frontend
```

### Step 5: Setup Nginx Reverse Proxy

**Nginx Configuration** (`/etc/nginx/sites-available/k1`):

```nginx
upstream k1_backend {
    server localhost:8000;
}

upstream k1_frontend {
    server localhost:3000;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # API proxy
    location /api/ {
        proxy_pass http://k1_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://k1_frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Enable and start Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/k1 /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup SSL with Let's Encrypt
sudo certbot certonly --nginx -d your-domain.com
```

---

## Production Configuration

### Environment Variables

**Backend** (`.env`):

```bash
# Core
ENVIRONMENT=production
DEBUG_MODE=false
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://k1_user:password@db-host:5432/k1
DATABASE_POOL_SIZE=20

# Cache
REDIS_URL=redis://redis-host:6379/0
REDIS_PASSWORD=your-redis-password

# LLM Providers
ANTHROPIC_API_KEY=sk-ant-your-key
OPENAI_API_KEY=sk-... (optional)
GEMINI_API_KEY=... (optional)

# Security
SECRET_KEY=your-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=app-password

# Upload Storage
UPLOAD_DIR=/var/lib/k1/uploads
MAX_UPLOAD_SIZE_MB=500

# Rate Limiting
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_PERIOD_SECONDS=60

# Branding
APP_NAME=Kaison K1
APP_VERSION=7.0
```

### Database Setup

```bash
# Create production database with backups
sudo -u postgres psql << EOF
CREATE DATABASE k1_prod;
CREATE USER k1_prod WITH PASSWORD 'very-secure-password';
GRANT ALL PRIVILEGES ON DATABASE k1_prod TO k1_prod;

-- Enable extensions
\c k1_prod
CREATE EXTENSION pg_trgm;
CREATE EXTENSION pgcrypto;
CREATE EXTENSION plpgsql;
EOF

# Initialize schema
cd apps/backend
python -m alembic upgrade head
```

---

## Monitoring & Maintenance

### Application Monitoring

```bash
# Check service status
sudo systemctl status k1-backend k1-frontend

# View logs
sudo journalctl -u k1-backend -f
sudo journalctl -u k1-frontend -f

# Monitor resources
top  # or htop
df -h
du -sh /var/lib/k1/*
```

### Database Maintenance

```bash
# Backup database
sudo -u postgres pg_dump k1_prod | gzip > /backups/k1_$(date +%Y%m%d).sql.gz

# Vacuum and analyze
sudo -u postgres psql -d k1_prod -c "VACUUM ANALYZE;"

# Reindex
sudo -u postgres psql -d k1_prod -c "REINDEX DATABASE k1_prod;"

# Setup automated backups (cron)
# Add to crontab: 0 2 * * * /usr/local/bin/backup-k1.sh
```

### Log Rotation

```bash
# /etc/logrotate.d/k1
/var/log/k1/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 k1 k1
}
```

---

## Scaling

### Horizontal Scaling (Multiple Backends)

```bash
# Deploy multiple backend instances
for i in {1..3}; do
  gcloud run deploy k1-backend-$i \
    --image gcr.io/$GCP_PROJECT_ID/k1-backend:latest \
    --platform managed \
    --region $GCP_REGION
done

# Load balance with Cloud Load Balancer
gcloud compute backend-services add-backend k1-service \
  --instance-group=k1-backends-group \
  --global
```

### Vertical Scaling

**Increase resource allocation:**

```bash
# GCP Cloud Run
gcloud run services update k1-backend \
  --memory 4Gi \
  --cpu 2

# On-premises: Update systemd service and increase PostgreSQL connections
```

### Database Scaling

```bash
# Switch to managed PostgreSQL (GCP Cloud SQL)
gcloud sql instances patch k1-db \
  --tier=db-custom-4-16384

# Enable read replicas for scaling queries
gcloud sql instances patch k1-db \
  --enable-bin-log \
  --backup-start-time=02:00
```

---

## Summary

| Deployment Type | Time | Complexity | Cost |
|---|---|---|---|
| Local Dev | 5 min | Low | $0 |
| Docker Compose | 10 min | Low | $0 |
| GCP Cloud Run | 15 min | Medium | $50-200/mo |
| On-Premises | 1-2 hrs | High | $500-5000/mo |

**Next Steps:**
- Monitor application health and logs
- Setup automated backups
- Configure firewalls and security groups
- Train team on operations and troubleshooting

See [KAI_SECURITY_SETUP_GUIDE.md](./KAI_SECURITY_SETUP_GUIDE.md) for detailed security hardening.

