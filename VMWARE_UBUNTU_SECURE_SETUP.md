# Kaison K1 - VMware Ubuntu 22.04 Secure Setup Guide

**Complete guide for deploying K1 in an isolated, secure virtual environment**

---

## Table of Contents

1. [Architecture & Isolation](#architecture--isolation)
2. [VMware Configuration](#vmware-configuration)
3. [Ubuntu 22.04 Hardening](#ubuntu-2204-hardening)
4. [Network Security](#network-security)
5. [K1 Installation & Hardening](#k1-installation--hardening)
6. [Database Security](#database-security)
7. [API Security](#api-security)
8. [Monitoring & Logging](#monitoring--logging)
9. [Compliance & Legal](#compliance--legal)
10. [Backup & Disaster Recovery](#backup--disaster-recovery)
11. [Complete Setup Script](#complete-setup-script)
12. [Testing & Verification](#testing--verification)

---

## Architecture & Isolation

### Why VM for K1?

```
BENEFITS OF VMWARE ISOLATION:
├─ Sandboxing: K1 contained, cannot access host files
├─ Network Control: Isolated virtual network
├─ Snapshot Security: Rollback if compromised
├─ Multi-instance: Run multiple K1 instances safely
├─ Compliance: Separate scanning from host
├─ Testing: Safe environment for tool development
└─ Easy Cleanup: Delete VM and start fresh
```

### Recommended Architecture

```
┌─────────────────────────────────────┐
│   YOUR HOST MACHINE (Lenovo V15)    │
│   - Main OS (Windows/macOS/Linux)   │
│   - Personal data stays here        │
│   - Limited K1 interaction          │
└────────────────┬────────────────────┘
                 │
    ┌────────────▼──────────────┐
    │   VMware Workstation      │
    │   - Hypervisor            │
    │   - Network bridge        │
    │   - USB/Disk passthrough  │
    └────────────┬──────────────┘
                 │
    ┌────────────▼──────────────────────────────┐
    │   VM: Ubuntu 22.04 (K1 Isolated)         │
    │   - 8-16 GB RAM (from your 40GB)         │
    │   - 100-200 GB disk (from your 2TB)      │
    │   - Private network (172.16.0.x)         │
    │   - Firewall enabled                     │
    │   - No direct internet (via proxy)       │
    │   - Audited & logged                     │
    └─────────────────────────────────────────┘
                 │
    ┌────────────▼──────────────────┐
    │   K1 Services (Isolated)      │
    │   - Backend API (8000)        │
    │   - Frontend (5173)           │
    │   - PostgreSQL (5432)         │
    │   - Redis (6379)              │
    │   - All on private network    │
    └───────────────────────────────┘
```

---

## VMware Configuration

### Step 1: VMware Setup on Your Host

#### Download & Install VMware Workstation Pro (Recommended)

```bash
# For Windows/macOS
# Download from: https://www.vmware.com/products/workstation/workstation-pro.html
# License: $179 (one-time) or use free ESXi if hosting multiple VMs

# For Linux
# VMware Workstation Player (free) or Pro (paid)
```

#### Allocate Resources Wisely (You have 40GB RAM, 2TB storage)

```
FROM YOUR LENOVO V15 G2 (40GB RAM, 2TB storage):

Allocation to VM:
├─ RAM: 12-16 GB (leave 24 GB for host)
├─ vCPU: 4 cores (leave 4 for host)
├─ Disk: 150 GB SSD (leave 1.85TB free)
└─ Network: Bridged + private network

Host Remains Responsive:
├─ RAM: 24 GB available
├─ CPU: 4 cores for host OS
└─ Storage: 1.85 TB free for files
```

### Step 2: Create New Virtual Machine

#### In VMware Workstation:

```
File → New Virtual Machine

1. INSTALLER SOURCE
   ├─ ISO: ubuntu-22.04.1-desktop-amd64.iso
   └─ Download: https://ubuntu.com/download/desktop

2. VIRTUAL MACHINE NAME
   ├─ Name: "K1-Secure-Instance-01"
   ├─ Location: Store on external 1TB SSD
   └─ Type: Linux → Ubuntu 64-bit

3. MEMORY & PROCESSORS
   ├─ Memory: 14 GB
   ├─ Processors: 4 cores
   └─ Enable 3D acceleration: ✓

4. HARD DISK
   ├─ Size: 150 GB
   ├─ Type: NVME (if available)
   ├─ Allocation: Thick provision (faster, more secure)
   └─ Location: External SSD (/media/external/vms/)

5. NETWORK ADAPTER
   ├─ Adapter 1: Bridged (for internet access)
   ├─ Adapter 2: Host-only (isolated network)
   └─ Connected: ✓

6. ADVANCED OPTIONS
   ├─ UEFI firmware: ✓ (more secure)
   ├─ I/O acceleration: ✓
   ├─ Isolate VM guest caches: ✓
   └─ 3D graphics acceleration: ✓
```

### Step 3: VMware Security Settings

#### Edit VMware Configuration

```bash
# Windows: C:\Users\[USER]\AppData\Roaming\VMware\preferences.ini
# Linux/Mac: ~/.vmware/preferences

# Add security settings:
cat >> ~/.vmware/preferences << 'EOF'

# Security hardening
isolation.tools.hgfs.disable = "TRUE"
isolation.tools.dnd.disable = "TRUE"
isolation.tools.copy.disable = "TRUE"
isolation.tools.paste.disable = "TRUE"
isolation.ghi.host.allowaccesstovmrc = "FALSE"
tools.guestlib.enableHostInfo = "FALSE"
devices.hotplug = "FALSE"

# Performance
prefvmx.maxMemMB = "14000"
prefvmx.useRecommendedLockedMemSize = "TRUE"

# Logging
logging = "TRUE"
log.keepOld = "10"
EOF
```

#### Enable VM Logging

```bash
# Right-click VM → Settings → Options → Logging
├─ Enable logging: ✓
├─ Log location: /var/log/vmware/
└─ Keep 10 log files
```

### Step 4: VMware Snapshots (Security Checkpoints)

```bash
# Create Pre-K1 Snapshot
VM Menu → Snapshot → Take Snapshot

# Before Installing K1:
├─ Name: "Ubuntu-Base-Hardened"
├─ Description: "Clean Ubuntu 22.04 after hardening, before K1"
└─ Snapshot size: ~5 GB

# After K1 Installation:
├─ Name: "K1-Ready"
├─ Description: "K1 fully installed and tested"
└─ Snapshot size: ~20 GB

# Benefits:
├─ Quick rollback if issues occur
├─ Easy testing of configurations
├─ Can revert to clean state instantly
└─ No data loss during experiments
```

---

## Ubuntu 22.04 Hardening

### Step 1: Initial Installation

```bash
# Boot VM from ISO
# Choose: Minimal Installation (no extra bloat)

# Keyboard layout: Your preference
# Network: DHCP (we'll configure static later)
# Storage: Use entire virtual disk
# Users: Create user "k1admin" with strong password
```

### Step 2: Post-Installation Updates

```bash
# SSH into VM (or use VMware console)
ssh k1admin@[VM_IP]

# Update everything
sudo apt update
sudo apt upgrade -y
sudo apt dist-upgrade -y
sudo apt autoremove -y
sudo apt autoclean -y

# Reboot
sudo reboot
```

### Step 3: Kernel Hardening

```bash
# Add security parameters to GRUB
sudo nano /etc/default/grub

# Find: GRUB_CMDLINE_LINUX_DEFAULT
# Change from:
# GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"

# To:
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash apparmor=1 security=apparmor slub_debug=FZP module.sig_enforce=1 randomize_va_space=2 panic=10"

# Save (Ctrl+O, Enter, Ctrl+X)

# Apply changes
sudo update-grub
sudo reboot
```

### Step 4: Install Essential Security Tools

```bash
# Firewall
sudo apt install -y ufw

# Intrusion detection
sudo apt install -y aide aide-common

# Security monitoring
sudo apt install -y auditd audispd-plugins

# File integrity
sudo apt install -y tripwire

# Vulnerability scanning
sudo apt install -y lynis

# System hardening
sudo apt install -y fail2ban

# SSL/TLS
sudo apt install -y openssl ca-certificates
```

### Step 5: Configure UFW Firewall

```bash
# Enable UFW
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable

# Allow SSH (CRITICAL - or you'll lock yourself out!)
sudo ufw allow 22/tcp

# For K1 Services (later):
# sudo ufw allow 8000/tcp  # Backend API
# sudo ufw allow 5173/tcp  # Frontend (development only)
# sudo ufw allow 5432/tcp  # PostgreSQL (localhost only)

# Allow specific outbound (for LLM API calls)
sudo ufw allow out to any port 443  # HTTPS

# Verify rules
sudo ufw show added
```

### Step 6: Harden SSH

```bash
# Backup original
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Edit SSH configuration
sudo nano /etc/ssh/sshd_config

# Change/add these settings:
Port 2222                          # Change from default 22
PermitRootLogin no                 # Never allow root login
PasswordAuthentication no           # Force SSH keys only
PubkeyAuthentication yes
X11Forwarding no                   # Disable X11
AllowUsers k1admin                 # Only this user
Protocol 2                         # SSH2 only
ClientAliveInterval 300            # Timeout after 5 min
ClientAliveCountMax 2              # Disconnect after 2 timeouts
LogLevel VERBOSE                   # Detailed logging
MaxAuthTries 3                     # Max 3 login attempts
MaxSessions 10                     # Max 10 concurrent sessions

# Restart SSH
sudo systemctl restart ssh

# Create SSH key pair (on your host machine):
ssh-keygen -t ed25519 -C "k1-vm-key" -f ~/.ssh/k1_vm_key -N "strong_passphrase"

# Copy public key to VM
ssh-copy-id -i ~/.ssh/k1_vm_key.pub -p 2222 k1admin@[VM_IP]

# Test connection
ssh -i ~/.ssh/k1_vm_key -p 2222 k1admin@[VM_IP]
```

### Step 7: Configure AppArmor (MAC - Mandatory Access Control)

```bash
# Verify AppArmor is enabled
sudo aa-enabled

# Check status
sudo systemctl status apparmor

# Make it strict
sudo aa-enforce /etc/apparmor.d/*

# Create K1 AppArmor profile
sudo nano /etc/apparmor.d/usr.bin.python3

# Add:
#include <tunables/global>

/usr/bin/python3 {
  #include <abstractions/base>
  #include <abstractions/python>
  #include <abstractions/nameservice>

  /home/k1admin/kai/** rw,
  /tmp/** rw,
  /var/log/k1/** w,

  deny /etc/shadow r,
  deny /etc/sudoers r,
  deny /root/** r,
}

# Apply
sudo apparmor_parser -r /etc/apparmor.d/usr.bin.python3
```

### Step 8: Enable Audit Logging

```bash
# Start auditd
sudo systemctl enable auditd
sudo systemctl start auditd

# Add audit rules
sudo nano /etc/audit/rules.d/k1.rules

# Add:
# System calls
-a always,exit -F arch=b64 -S execve -F auid>=1000 -F auid!=-1 -k exec
-a always,exit -F arch=b32 -S execve -F auid>=1000 -F auid!=-1 -k exec

# File access
-w /home/k1admin/kai/ -p wa -k k1_modifications
-w /etc/security/ -p wa -k security_modifications
-w /var/log/ -p wa -k log_modifications

# Network connections
-a always,exit -F arch=b64 -S connect -S sendto -S recvfrom -S bind -S listen -F auid>=1000 -F auid!=-1 -k network

# Reload
sudo service auditd restart
sudo auditctl -l  # List all rules
```

### Step 9: Disable Unnecessary Services

```bash
# Check running services
sudo systemctl list-units --type=service --state=running

# Disable unnecessary ones:
sudo systemctl disable cups                    # Printing (not needed)
sudo systemctl disable avahi-daemon           # mDNS (not needed)
sudo systemctl disable isc-dhcp-server        # DHCP (not needed)
sudo systemctl disable snmpd                  # SNMP (not needed)
sudo systemctl disable rsync                  # Rsync (not needed)
sudo systemctl disable nis                    # NIS (not needed)

# Verify they're stopped
sudo systemctl stop [service_name]
```

### Step 10: Configure sudo with Logging

```bash
# Edit sudoers file safely
sudo visudo

# Add at end:
Defaults use_pty
Defaults logfile="/var/log/sudo.log"
Defaults log_host, log_year, logfile="/var/log/sudo.log"
Defaults requiretty
Defaults passwd_timeout=1
Defaults timestamp_timeout=5
Defaults lecture="always"

# Create sudo log
sudo touch /var/log/sudo.log
sudo chmod 640 /var/log/sudo.log
```

### Step 11: File System Hardening

```bash
# Mount with secure options
sudo nano /etc/fstab

# Find /home line and modify to:
/dev/mapper/ubuntu--vg-ubuntu--lv /home ext4 defaults,nosuid,nodev,noexec 0 2

# Find /tmp line and modify to:
tmpfs /tmp tmpfs defaults,rw,nosuid,nodev,noexec,relatime 0 0

# Find /var line and modify to:
tmpfs /var tmpfs defaults,rw,nosuid,nodev,noexec,relatime 0 0

# Reload
sudo mount -o remount /home
sudo mount -o remount /tmp
sudo mount -o remount /var
```

### Step 12: Automatic Security Updates

```bash
# Install unattended-upgrades
sudo apt install -y unattended-upgrades apt-listchanges

# Configure
sudo nano /etc/apt/apt.conf.d/50unattended-upgrades

# Uncomment/modify:
Unattended-Upgrade::Packages {
    "k1-related-packages";
};

Unattended-Upgrade::Mail "k1admin@localhost";
Unattended-Upgrade::MailReport "on-change";

# Enable
sudo dpkg-reconfigure -plow unattended-upgrades

# Verify
sudo systemctl enable unattended-upgrades
```

### Step 13: Verify Hardening

```bash
# Run Lynis security audit
sudo lynis audit system

# Review findings
sudo cat /var/log/lynis-report.dat

# Expected score: 70+ (very good)
```

---

## Network Security

### Step 1: Static IP Configuration

```bash
# Get current network info
ip addr show
ip route show

# Edit netplan configuration
sudo nano /etc/netplan/00-installer-config.yaml

# Configure:
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: no
      addresses:
        - 172.16.1.100/24
      gateway4: 172.16.1.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
    eth1:
      dhcp4: yes

# Apply
sudo netplan apply

# Verify
ip addr show
```

### Step 2: Firewall with Specific Rules

```bash
# Reset firewall (start fresh)
sudo ufw reset

# Set defaults
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable

# Allow SSH (CRITICAL)
sudo ufw allow 22/tcp

# For K1 Backend (internal only)
sudo ufw allow from 172.16.1.0/24 to any port 8000

# For K1 Frontend (development only)
sudo ufw allow from 172.16.1.0/24 to any port 5173

# For PostgreSQL (localhost only)
sudo ufw allow from 127.0.0.1 to any port 5432

# Allow outbound HTTPS (for LLM APIs)
sudo ufw allow out 443/tcp

# Verify
sudo ufw status verbose
```

### Step 3: VPN/Proxy for Internet Access (Optional but Recommended)

```bash
# If you want K1's LLM calls to go through proxy:

# Install squid proxy (on separate machine or VM)
# Or use VPN: apt install -y openvpn

# Configure K1 to use proxy
# In /etc/environment:
export HTTP_PROXY=http://proxy.local:3128
export HTTPS_PROXY=http://proxy.local:3128
export NO_PROXY=localhost,127.0.0.1

# Or configure in Python:
# os.environ['HTTPS_PROXY'] = 'http://proxy.local:3128'
```

### Step 4: DNS Security (DNSSEC)

```bash
# Configure DNSSEC
sudo nano /etc/systemd/resolved.conf

# Add:
DNSSEC=yes
DNS=8.8.8.8 8.8.4.4
FallbackDNS=1.1.1.1

# Apply
sudo systemctl restart systemd-resolved

# Verify
systemd-resolve --status
```

---

## K1 Installation & Hardening

### Step 1: Create K1 User (Separate from Admin)

```bash
# Create non-root user for K1
sudo useradd -m -s /bin/bash -G sudo k1_app

# Set strong password
sudo passwd k1_app

# Allow sudo without password (for services only)
sudo visudo
# Add: k1_app ALL=(ALL) NOPASSWD: /usr/bin/systemctl
```

### Step 2: Install K1 Dependencies

```bash
# Switch to k1_app user
su - k1_app

# Install Python & Node
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo apt install -y nodejs npm
sudo apt install -y git curl wget

# Verify versions
python3.11 --version  # 3.11.x
node --version        # v18+
npm --version         # 9+
```

### Step 3: Clone K1 Repository

```bash
# Create work directory
mkdir -p /home/k1_app/k1
cd /home/k1_app/k1

# Clone from GitHub
git clone https://github.com/mrmsoc09/Kaison_Latest_Build.git
cd Kaison_Latest_Build

# Verify you got latest code
git log --oneline -1
```

### Step 4: Install K1 Backend

```bash
cd apps/backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Verify installation
python -c "import anthropic; print('✓ Anthropic SDK installed')"
python -c "import fastapi; print('✓ FastAPI installed')"
```

### Step 5: Install K1 Frontend

```bash
cd ../frontend

# Install Node modules
npm install

# Build for production (not dev)
npm run build

# Verify build
ls -la dist/
```

### Step 6: Configure K1 Environment Variables

```bash
# Create secure .env file
cd ../backend
nano .env

# Add (with YOUR actual values):
# Core Settings
ENVIRONMENT=production
DEBUG_MODE=false
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://k1_user:STRONG_PASSWORD@localhost:5432/k1_db
DATABASE_POOL_SIZE=20

# Cache
REDIS_URL=redis://localhost:6379/0

# LLM Providers (choose at least one)
ANTHROPIC_API_KEY=sk-ant-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
# GEMINI_API_KEY=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Security
SECRET_KEY=GENERATE_WITH: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Email (for alerts)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=app-specific-password

# Security Scanning
SCAN_TIMEOUT_SECONDS=3600
MAX_CONCURRENT_SCANS=5
AUDIT_LOG_RETENTION_DAYS=730

# Logging
LOG_FILE=/var/log/k1/backend.log
LOG_ROTATION_SIZE_MB=100
LOG_BACKUP_COUNT=10

# Set permissions
chmod 600 .env
```

### Step 7: Database Setup (PostgreSQL)

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start service
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create K1 database and user
sudo -u postgres psql << 'EOF'

-- Create database
CREATE DATABASE k1_db;

-- Create user
CREATE USER k1_user WITH PASSWORD 'STRONG_PASSWORD_HERE';

-- Grant permissions
ALTER ROLE k1_user SET client_encoding TO 'utf8';
ALTER ROLE k1_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE k1_user SET default_transaction_deferrable TO on;
ALTER ROLE k1_user SET default_transaction_read_committed TO on;

GRANT ALL PRIVILEGES ON DATABASE k1_db TO k1_user;

-- Create tables (K1 will do this)
EOF

# Harden PostgreSQL
sudo nano /etc/postgresql/14/main/postgresql.conf

# Change:
listen_addresses = 'localhost'         # Only localhost
password_encryption = 'scram-sha-256'  # Secure password hashing
log_connections = on
log_disconnections = on
log_statement = 'all'                  # Log all queries
log_min_duration_statement = 0
logging_collector = on

# Restart
sudo systemctl restart postgresql
```

### Step 8: Redis Cache Setup

```bash
# Install Redis
sudo apt install -y redis-server

# Configure Redis securely
sudo nano /etc/redis/redis.conf

# Change:
bind 127.0.0.1                         # Local only
protected-mode yes
port 6379
requirepass STRONG_PASSWORD_HERE       # Require auth
databases 16
appendonly yes                         # AOF persistence
appendfsync everysec                   # Sync every second
maxclients 10000
timeout 300                            # Disconnect idle clients

# Restart
sudo systemctl enable redis-server
sudo systemctl restart redis-server

# Test
redis-cli ping                         # Should return PONG
```

### Step 9: Create Systemd Services for K1

#### Backend Service

```bash
# Create service file
sudo nano /etc/systemd/system/k1-backend.service

# Add:
[Unit]
Description=Kaison K1 Backend API
After=postgresql.service redis-server.service network.target
Wants=postgresql.service redis-server.service

[Service]
Type=notify
User=k1_app
Group=k1_app
WorkingDirectory=/home/k1_app/k1/Kaison_Latest_Build/apps/backend
Environment="PATH=/home/k1_app/k1/Kaison_Latest_Build/apps/backend/venv/bin"
Environment="DATABASE_URL=postgresql://k1_user:PASSWORD@localhost:5432/k1_db"
Environment="ANTHROPIC_API_KEY=sk-ant-..."
EnvironmentFile=/home/k1_app/k1/Kaison_Latest_Build/apps/backend/.env
ExecStart=/home/k1_app/k1/Kaison_Latest_Build/apps/backend/venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable k1-backend
sudo systemctl start k1-backend

# Check status
sudo systemctl status k1-backend
```

#### Frontend Service (Production)

```bash
# For production, use Nginx instead of dev server
sudo apt install -y nginx

# Create nginx config
sudo nano /etc/nginx/sites-available/k1

[Server config - see below]

# Enable
sudo ln -s /etc/nginx/sites-available/k1 /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

#### Nginx Configuration for K1

```bash
sudo nano /etc/nginx/sites-available/k1

# Add:
upstream k1_backend {
    server 127.0.0.1:8000;
}

server {
    listen 5173 ssl http2;
    server_name localhost;

    # SSL/TLS Configuration
    ssl_certificate /etc/ssl/certs/k1-self-signed.crt;
    ssl_certificate_key /etc/ssl/private/k1-self-signed.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    # Logging
    access_log /var/log/nginx/k1_access.log;
    error_log /var/log/nginx/k1_error.log;

    # Frontend
    root /home/k1_app/k1/Kaison_Latest_Build/apps/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API Proxy
    location /api/ {
        proxy_pass http://k1_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # Deny access to sensitive files
    location ~ /\.env {
        deny all;
    }

    location ~ /\.git {
        deny all;
    }
}
```

### Step 10: SSL/TLS Certificates

```bash
# Generate self-signed certificate (for internal use)
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/k1-self-signed.key \
  -out /etc/ssl/certs/k1-self-signed.crt

# For production, use Let's Encrypt (if exposed to internet)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com
```

---

## Database Security

### Backup Strategy

```bash
# Create backup script
nano /home/k1_app/backup_k1.sh

#!/bin/bash
BACKUP_DIR="/home/k1_app/k1/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
pg_dump -U k1_user k1_db | gzip > "$BACKUP_DIR/k1_db_$DATE.sql.gz"

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb "$BACKUP_DIR/redis_$DATE.rdb"

# Audit logs backup
tar -czf "$BACKUP_DIR/audit_logs_$DATE.tar.gz" /var/log/k1/

# Keep only last 30 days
find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/k1_db_$DATE.sql.gz"

# Make executable
chmod +x /home/k1_app/backup_k1.sh

# Schedule with cron (daily at 2 AM)
crontab -e
0 2 * * * /home/k1_app/backup_k1.sh
```

---

## API Security

### Input Validation

```python
# In K1 backend - validate all inputs
from pydantic import BaseModel, validator, constr

class ScanRequest(BaseModel):
    target: constr(regex=r'^[a-zA-Z0-9.-]+$')  # Only alphanumeric, dots, hyphens
    user_id: constr(regex=r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')  # Email
    scope: constr(min_length=1, max_length=2048)  # Reasonable length

    @validator('target')
    def validate_target(cls, v):
        # Prevent SSRF
        if v in ['localhost', '127.0.0.1', '0.0.0.0']:
            raise ValueError('Invalid target')
        return v
```

### Rate Limiting

```python
# In FastAPI app
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/v1/kai/scan/osint")
@limiter.limit("10/minute")  # Max 10 scans per minute
async def scan_osint(request: ScanRequest):
    # Process scan
    pass
```

### CORS & CSRF

```python
# Configure CORS strictly
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Only local frontend
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# CSRF tokens
from fastapi_csrf_protect import CsrfProtect

@app.post("/api/v1/kai/authorize")
@CsrfProtect.csrf_protect
async def authorize(request: AuthorizeRequest, csrf_protect: CsrfProtect = Depends()):
    pass
```

---

## Monitoring & Logging

### Centralized Logging

```bash
# Install ELK Stack or Splunk (optional but recommended)
sudo apt install -y elasticsearch logstash kibana

# Or use Loki for lightweight logging
sudo apt install -y promtail

# Configure K1 logging
cat > /var/log/k1/k1-logging.conf << 'EOF'
[loggers]
keys=root,k1_backend

[handlers]
keys=console,file,syslog

[formatters]
keys=detailed

[logger_root]
level=INFO
handlers=console,file,syslog

[logger_k1_backend]
level=DEBUG
qualname=k1_backend
handlers=console,file,syslog
propagate=0

[handler_console]
class=StreamHandler
level=INFO
formatter=detailed
args=(sys.stdout,)

[handler_file]
class=FileHandler
level=DEBUG
formatter=detailed
args=('/var/log/k1/backend.log', 'a')

[handler_syslog]
class=handlers.SysLogHandler
level=WARNING
formatter=detailed
args=('/dev/log', handlers.SysLogHandler.LOG_LOCAL0)

[formatter_detailed]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
datefmt=%Y-%m-%d %H:%M:%S
EOF
```

### Monitoring Dashboard

```bash
# Install Prometheus + Grafana
sudo apt install -y prometheus grafana-server

# Start services
sudo systemctl enable prometheus grafana-server
sudo systemctl start prometheus grafana-server

# Access Grafana: http://localhost:3000
# Default credentials: admin/admin (change immediately!)
```

### Security Monitoring

```bash
# Monitor for suspicious activities
sudo apt install -y osquery wazuh-agent

# Create custom monitoring rules
sudo nano /var/lib/wazuh/ruleset/rules/local_rules.xml

<group name="K1">
  <rule id="100001" level="5">
    <pattern>failed.*authorization</pattern>
    <description>K1 Authorization Failed</description>
  </rule>

  <rule id="100002" level="7">
    <pattern>multiple.*failed.*scans</pattern>
    <description>Multiple Failed Scans Detected</description>
  </rule>
</group>
```

---

## Compliance & Legal

### Important: Responsible Disclosure

```
⚠️ CRITICAL LEGAL REMINDERS:

1. ONLY SCAN TARGETS YOU OWN OR HAVE WRITTEN PERMISSION FOR
   ├─ Bug bounty programs (HackerOne, Bugcrowd, etc.)
   ├─ Your own applications
   ├─ Authorized penetration testing
   └─ NEVER unauthorized scanning (it's illegal)

2. K1's Authorization System Enforces This
   ├─ Requires certificate of authorization
   ├─ Logs all operations immutably
   ├─ Can be audited for compliance
   └─ Proof of authorized scanning

3. Use K1 Ethically
   ├─ Follow platform rules (HackerOne, etc.)
   ├─ Report vulnerabilities responsibly
   ├─ Follow responsible disclosure timelines
   ├─ Don't exceed scope
   └─ Document everything

4. Your VM Should Reflect This
   ├─ Clean audit logs showing authorization
   ├─ All scans have proof of permission
   ├─ Can show to regulators/platforms
   └─ Professional setup = professional operation
```

### Audit Trail Setup

```bash
# Ensure all K1 operations logged
sudo mkdir -p /var/log/k1
sudo chown k1_app:k1_app /var/log/k1
sudo chmod 750 /var/log/k1

# Enable audit trail in K1 config
AUDIT_LOG_FILE=/var/log/k1/audit_trail.log
AUDIT_LOG_RETENTION_DAYS=730  # 2 years

# Verify logging
tail -f /var/log/k1/audit_trail.log
```

### Documentation

```bash
# Keep records of:
mkdir -p /home/k1_app/k1/compliance

# 1. Authorizations
cp /home/k1_app/k1/authorizations.json /home/k1_app/k1/compliance/

# 2. Scan requests
cp /home/k1_app/k1/scan_requests.json /home/k1_app/k1/compliance/

# 3. Results
cp /home/k1_app/k1/scan_results.json /home/k1_app/k1/compliance/

# Sign documentation (optional but professional)
gpg --sign compliance/audit_trail.log
```

---

## Backup & Disaster Recovery

### Full VM Backup

```bash
# In VMware:
1. VM → Snapshot → Take Snapshot
   ├─ Name: "K1-Prod-Backup-2025-02-02"
   ├─ Description: "Full production backup"
   └─ Snapshot size: 50-100 GB

2. Create Clone
   VM → Manage → Clone
   ├─ Full Clone (independent copy)
   ├─ Name: "K1-Backup-Instance"
   └─ Store on external SSD

3. Export OVA
   File → Export → Export OVA
   ├─ Name: "K1-Ubuntu-Backup.ova"
   ├─ Location: External drive
   └─ For recovery/migration
```

### Recovery Procedure

```bash
# If VM corrupted:

# Option 1: Snapshot Rollback (5 minutes)
VM → Snapshot → "K1-Prod-Backup-2025-02-02" → Restore

# Option 2: Clone Activation (10 minutes)
1. Power off corrupted VM
2. Power on clone ("K1-Backup-Instance")
3. Resume operations

# Option 3: Restore from OVA (20-30 minutes)
1. File → Open OVA
2. Select "K1-Ubuntu-Backup.ova"
3. Wait for import
4. Power on new VM
```

---

## Complete Setup Script

### One-Command Installation

```bash
#!/bin/bash
# Run on clean Ubuntu 22.04 VM
# curl -sSL https://raw.githubusercontent.com/mrmsoc09/Kaison_Latest_Build/main/scripts/setup_vm_secure.sh | bash

set -e

echo "🔐 Kaison K1 - Secure VM Setup"
echo "================================"

# 1. Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
echo "📦 Installing dependencies..."
sudo apt install -y python3.11 python3.11-venv python3.11-dev
sudo apt install -y nodejs npm git curl wget
sudo apt install -y postgresql redis-server nginx

# 3. Security tools
echo "🔒 Installing security tools..."
sudo apt install -y ufw fail2ban auditd apparmor

# 4. Harden system
echo "🛡️  Hardening system..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw enable

# 5. Clone K1
echo "📥 Cloning K1 repository..."
git clone https://github.com/mrmsoc09/Kaison_Latest_Build.git k1
cd k1

# 6. Setup backend
echo "🚀 Setting up backend..."
cd apps/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 7. Setup frontend
echo "🎨 Setting up frontend..."
cd ../frontend
npm install
npm run build

# 8. Setup systemd services
echo "⚙️  Setting up services..."
sudo cp ../backend/k1-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable k1-backend

# 9. Final verification
echo "✅ Verification..."
python -c "import anthropic; print('✓ K1 Ready')"

echo ""
echo "✅ Setup complete!"
echo "🎯 Next steps:"
echo "1. Configure .env file: nano apps/backend/.env"
echo "2. Start services: sudo systemctl start k1-backend"
echo "3. Access frontend: https://localhost:5173"
echo "4. Default credentials: check documentation"
echo ""
```

---

## Testing & Verification

### Pre-Launch Checklist

```bash
#!/bin/bash
# Verify K1 is secure and ready

echo "🔍 K1 Security Verification"
echo "============================"

# 1. Firewall check
echo "1. Firewall Status:"
sudo ufw status verbose

# 2. SSH security
echo "2. SSH Configuration:"
sudo sshctl -C "PermitRootLogin"
sudo sshctl -C "PasswordAuthentication"

# 3. Services running
echo "3. Services Status:"
sudo systemctl status k1-backend
sudo systemctl status postgresql
sudo systemctl status redis-server

# 4. Port checks
echo "4. Open Ports:"
sudo ss -tlnp | grep LISTEN

# 5. Audit logs
echo "5. Recent Audit Logs:"
sudo ausearch -m execute --format text | tail -10

# 6. Security scans
echo "6. Security Audit:"
sudo lynis audit system | grep -E "^(Warning|Suggestion)"

# 7. K1 Health Check
echo "7. K1 Backend Health:"
curl -k https://localhost:8000/health

# 8. Database check
echo "8. Database Status:"
sudo -u postgres psql -c "SELECT version();"

# 9. File integrity
echo "9. File Integrity Check:"
sudo aide --check 2>/dev/null || echo "First run - baseline created"

echo ""
echo "✅ Verification complete"
```

### Performance Benchmark

```bash
# Test K1 under load
apt install -y apache2-utils

# 100 requests, 10 concurrent
ab -n 100 -c 10 https://localhost:5173/

# Expected results:
# - Response time: <500ms
# - Success rate: 100%
# - Requests/sec: >20
```

---

## Summary: Secure K1 VM Setup

```
YOUR SETUP:
├─ Lenovo V15 G2 Host (40GB RAM, 2TB SSD)
│
├─ VMware Workstation Hypervisor
│  ├─ Isolated network
│  ├─ Snapshots for security
│  └─ Logging enabled
│
└─ Ubuntu 22.04 VM
   ├─ 14 GB RAM allocated
   ├─ 150 GB SSD storage
   ├─ Hardened kernel
   ├─ AppArmor MAC enabled
   ├─ Firewall (UFW)
   ├─ Audit logging
   ├─ SSH key-only auth
   ├─ Automatic security updates
   │
   ├─ K1 Services
   │  ├─ Backend (8000)
   │  ├─ Frontend (5173 SSL)
   │  ├─ PostgreSQL (5432)
   │  └─ Redis (6379)
   │
   ├─ Monitoring
   │  ├─ Prometheus
   │  ├─ Grafana
   │  ├─ ELK Stack (optional)
   │  └─ Audit trail
   │
   └─ Compliance
      ├─ Authorization logging
      ├─ Immutable audit trail
      ├─ Backup strategy
      └─ Disaster recovery
```

---

## Estimated Time to Complete

```
Task                           Time      Cumulative
─────────────────────────────────────────────────
1. VMware Setup                30 min    30 min
2. Ubuntu Installation         20 min    50 min
3. System Hardening            45 min    95 min
4. K1 Installation            30 min    125 min
5. Database Setup             20 min    145 min
6. Security Configuration     45 min    190 min
7. Testing & Verification     30 min    220 min

TOTAL: ~3.5-4 hours for production-ready secure K1 VM
```

---

## Quick Reference: Essential Commands

```bash
# Start/Stop K1
sudo systemctl start k1-backend
sudo systemctl stop k1-backend
sudo systemctl status k1-backend

# View logs
journalctl -u k1-backend -f
tail -f /var/log/k1/backend.log

# Database access
sudo -u postgres psql -d k1_db

# Redis access
redis-cli -a PASSWORD

# Firewall management
sudo ufw allow 8000/tcp
sudo ufw deny 8000/tcp
sudo ufw status

# System audit
sudo auditctl -l
sudo ausearch -m all

# Backup database
pg_dump -U k1_user k1_db | gzip > backup.sql.gz

# Restore database
gunzip < backup.sql.gz | psql -U k1_user k1_db

# Check VM resources
free -h
df -h
htop
```

---

## Next Steps

1. ✅ Create VM with resources from this guide
2. ✅ Run hardening script
3. ✅ Install K1 using setup script
4. ✅ Configure .env with your API keys
5. ✅ Verify all services running
6. ✅ Create authorizations in K1
7. ✅ Start hunting vulnerabilities safely & securely
8. ✅ Monitor audit logs
9. ✅ Maintain backups

**Your secure K1 environment is now production-ready!** 🚀

---

**Generated:** February 2, 2025
**Purpose:** Enterprise-grade K1 deployment on VMware
**Security Level:** ⭐⭐⭐⭐⭐ Production-Ready
**Compliance:** Authorized scanning, auditable, immutable logs

