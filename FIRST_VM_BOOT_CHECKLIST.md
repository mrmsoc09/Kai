# K1 on VMware - First Boot to Production Checklist

**Step-by-step instructions from fresh Ubuntu 22.04 VM to running K1**

Start here. Follow in order. Don't skip steps.

---

## INITIAL SETUP (15 minutes)

### Step 1: Boot Ubuntu & Complete Installation
**Time: 10 minutes**

```
1. Start the VM in VMware
2. Boot from Ubuntu 22.04 ISO
3. Click "Install Ubuntu"
4. Choose language: English
5. Keyboard layout: Your preference (or US)
6. Network: Auto DHCP (fine for now)
7. Storage: Use entire virtual disk
8. Installation type: Minimal Installation (recommended)
9. Create user:
   - Name: k1admin
   - Username: k1admin
   - Password: Strong_Password_Here_Min_16_Chars
   - Computer name: k1-vm
10. Click Install
11. Wait 5-10 minutes for completion
12. Remove ISO and reboot
```

### Step 2: First Login & Update
**Time: 5 minutes**

```bash
# After VM reboots, login with your password
# Open Terminal (Ctrl+Alt+T)

# Update everything
sudo apt update
sudo apt upgrade -y
sudo apt dist-upgrade -y
sudo apt autoremove -y

# Reboot
sudo reboot
```

✅ **Checkpoint 1: Ubuntu installed and updated**

---

## SECURITY HARDENING (30 minutes)

### Step 3: SSH Key Setup (CRITICAL)
**Time: 10 minutes**

```bash
# On your HOST machine (Lenovo), NOT in VM
# Open PowerShell (Windows) or Terminal (Mac/Linux)

# Generate SSH key
ssh-keygen -t ed25519 -C "k1-vm-key" -f ~/.ssh/k1_vm_key -N "your_passphrase"

# Output will show:
# Your public key is saved in: ~/.ssh/k1_vm_key.pub
# Your private key is saved in: ~/.ssh/k1_vm_key

# Note: If on Windows, use Git Bash or WSL
```

**Now in the VM:**

```bash
# Install SSH server
sudo apt install -y openssh-server openssh-client

# Create SSH directory
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Add your public key from host
# (Copy content of ~/.ssh/k1_vm_key.pub from your host)
nano ~/.ssh/authorized_keys

# Paste the public key (Ctrl+Shift+V)
# Save (Ctrl+O, Enter, Ctrl+X)

chmod 600 ~/.ssh/authorized_keys

# Verify SSH works
ssh-keygen -l -f ~/.ssh/authorized_keys
```

**Test from your host:**

```bash
# Get VM IP
ip addr show | grep inet

# SSH to VM (use the IP shown above)
ssh -i ~/.ssh/k1_vm_key -p 22 k1admin@[VM_IP]

# Should connect without password prompt (just passphrase for key)
# Type: exit
```

✅ **Checkpoint 2: SSH key-based auth working**

---

### Step 4: Firewall Setup
**Time: 5 minutes**

```bash
# In VM Terminal

# Install UFW
sudo apt install -y ufw

# Set defaults (deny all incoming)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (CRITICAL - don't lock yourself out!)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable

# Verify
sudo ufw status

# Output should show:
# Status: active
# To                         Action      From
# --                         ------      ----
# 22/tcp                     ALLOW       Anywhere
# 22/tcp (v6)                ALLOW       Anywhere (v6)
```

✅ **Checkpoint 3: Firewall active and SSH allowed**

---

### Step 5: Kernel Hardening
**Time: 5 minutes**

```bash
# Edit GRUB configuration
sudo nano /etc/default/grub

# Find the line starting with: GRUB_CMDLINE_LINUX_DEFAULT=
# Replace it with:
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash apparmor=1 security=apparmor"

# Save (Ctrl+O, Enter, Ctrl+X)

# Apply changes
sudo update-grub

# Reboot
sudo reboot
```

✅ **Checkpoint 4: Kernel hardened with AppArmor**

---

### Step 6: Install Security Tools
**Time: 5 minutes**

```bash
# After reboot, open Terminal

# Install security packages
sudo apt install -y ufw fail2ban auditd audispd-plugins

# Start audit daemon
sudo systemctl enable auditd
sudo systemctl start auditd

# Verify it's running
sudo systemctl status auditd

# Should show: active (running)
```

✅ **Checkpoint 5: Security tools installed**

---

## K1 INSTALLATION (45 minutes)

### Step 7: Install Dependencies
**Time: 10 minutes**

```bash
# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Install Node.js
sudo apt install -y nodejs npm

# Install Git & utilities
sudo apt install -y git curl wget

# Verify versions
python3.11 --version   # Should be 3.11.x
node --version          # Should be v18+
npm --version           # Should be 9+

# If any fails, run: sudo apt install -y [package]
```

✅ **Checkpoint 6: All dependencies installed**

---

### Step 8: Install Database & Cache
**Time: 10 minutes**

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Verify
sudo systemctl status postgresql

# Install Redis
sudo apt install -y redis-server

# Start Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Verify
sudo systemctl status redis-server

# Both should show: active (running)
```

✅ **Checkpoint 7: Database and cache installed**

---

### Step 9: Clone K1 Repository
**Time: 3 minutes**

```bash
# Go to home directory
cd ~

# Clone K1
git clone https://github.com/mrmsoc09/Kaison_Latest_Build.git kai

# Enter directory
cd kai

# Verify you got the latest
git log --oneline -1

# Should show: Phase 7 Complete: K1 unified platform...
```

✅ **Checkpoint 8: K1 repository cloned**

---

### Step 10: Setup Backend
**Time: 10 minutes**

```bash
# Navigate to backend
cd ~/kai/apps/backend

# Create virtual environment
python3.11 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install requirements
pip install -r requirements.txt

# This takes 3-5 minutes, be patient

# Verify installation
python -c "import anthropic; print('✓ Anthropic SDK OK')"
python -c "import fastapi; print('✓ FastAPI OK')"
python -c "import sqlalchemy; print('✓ SQLAlchemy OK')"

# All three should print ✓
```

✅ **Checkpoint 9: Backend dependencies installed**

---

### Step 11: Setup Frontend
**Time: 5 minutes**

```bash
# Navigate to frontend
cd ~/kai/apps/frontend

# Install Node modules
npm install

# Takes 2-3 minutes

# Build for production
npm run build

# Verify build succeeded
ls -la dist/

# Should show: index.html and other files
```

✅ **Checkpoint 10: Frontend built successfully**

---

## CONFIGURATION (20 minutes)

### Step 12: Configure Environment Variables
**Time: 10 minutes**

```bash
# Go to backend directory
cd ~/kai/apps/backend

# Create .env file
nano .env

# Paste the following (customize with YOUR values):
```

```
# Core Settings
ENVIRONMENT=production
DEBUG_MODE=false
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://k1_user:strong_password_123@localhost:5432/k1_db
DATABASE_POOL_SIZE=20

# Cache
REDIS_URL=redis://localhost:6379/0

# LLM Providers (add your API keys)
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE

# Security
SECRET_KEY=generate_with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Logging
LOG_FILE=/var/log/k1/backend.log
LOG_LEVEL=info
```

```bash
# To get your ANTHROPIC_API_KEY:
# 1. Go to https://console.anthropic.com
# 2. Create account if needed
# 3. Create API key
# 4. Paste key into .env

# After editing, save (Ctrl+O, Enter, Ctrl+X)

# Set permissions (security)
chmod 600 .env

# Verify it saved
cat .env | head -5
```

✅ **Checkpoint 11: Environment configured**

---

### Step 13: Setup PostgreSQL Database
**Time: 5 minutes**

```bash
# Switch to postgres user
sudo -u postgres psql

# You're now in PostgreSQL interactive mode

# Create database
CREATE DATABASE k1_db;

# Create user
CREATE USER k1_user WITH PASSWORD 'strong_password_123';

# Grant permissions
ALTER ROLE k1_user SET client_encoding TO 'utf8';
ALTER ROLE k1_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE k1_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE k1_db TO k1_user;

# Exit PostgreSQL
\q

# Verify from command line
PGPASSWORD=strong_password_123 psql -U k1_user -d k1_db -c "SELECT 1;" -h localhost

# Should print: 1
```

✅ **Checkpoint 12: PostgreSQL database ready**

---

### Step 14: Setup Firewall Rules for K1
**Time: 5 minutes**

```bash
# Backend API (internal only)
sudo ufw allow from 127.0.0.1 to any port 8000

# Frontend (development - internal only)
sudo ufw allow from 127.0.0.1 to any port 5173

# PostgreSQL (local only)
sudo ufw allow from 127.0.0.1 to any port 5432

# Redis (local only)
sudo ufw allow from 127.0.0.1 to any port 6379

# Verify rules
sudo ufw show added

# Should show all 4 rules above
```

✅ **Checkpoint 13: Firewall rules configured**

---

## START K1 SERVICES (10 minutes)

### Step 15: Start Backend
**Time: 2 minutes**

```bash
# In VM Terminal, navigate to backend
cd ~/kai/apps/backend

# Activate virtual environment
source venv/bin/activate

# Start backend
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

# Wait for output:
# INFO:     Uvicorn running on http://127.0.0.1:8000
# INFO:     Application startup complete

# DON'T close this terminal - keep it running
```

✅ **Checkpoint 14: Backend API running**

---

### Step 16: Start Frontend (New Terminal)
**Time: 2 minutes**

```bash
# OPEN A NEW TERMINAL in the VM
# (Ctrl+Alt+T opens new terminal, or use VMware console)

# Navigate to frontend
cd ~/kai/apps/frontend

# Start development server
npm run dev

# Wait for output:
# VITE v... ready in ... ms
# ➜ Local:   http://localhost:5173/

# DON'T close this terminal - keep it running
```

✅ **Checkpoint 15: Frontend running**

---

### Step 17: Verify K1 Works
**Time: 3 minutes**

```bash
# OPEN A NEW TERMINAL (third terminal)

# Test backend API
curl http://localhost:8000/health

# Should return: {"status":"ok"}

# If it hangs, backend may still be starting - wait 10 seconds

# Test database connection
curl -s http://localhost:8000/api/v1/kai/audit-logs | head -20

# Should return JSON (not an error)

# If you see connection error, check .env DATABASE_URL
```

✅ **Checkpoint 16: K1 services verified working**

---

### Step 18: Access Dashboard in Browser
**Time: 2 minutes**

```bash
# On your host machine (your Lenovo)
# Open browser

# Type: http://[VM_IP]:5173
# Replace [VM_IP] with your VM's IP address

# To find VM IP from the VM:
# hostname -I

# You should see:
# ✓ Kaison K1 header
# ✓ Dashboard tab active
# ✓ System stats showing "0 Tools" (not loaded yet)
# ✓ Green branding colors
```

✅ **Checkpoint 17: Dashboard accessible**

---

## CREATE FIRST AUTHORIZATION (5 minutes)

### Step 19: Create Authorization Certificate
**Time: 5 minutes**

```bash
# From your host machine, open Terminal/PowerShell

# Create authorization certificate
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  -H "Content-Type: application/json" \
  -d '{
    "authorization_type": "bug_bounty_platform",
    "target": "example.com",
    "authorized_by": "your-email@example.com",
    "duration_days": 365,
    "scope": "domain_wildcard",
    "methods": "osint,vulnerability_scanning,web_testing"
  }'

# You should see response:
# {
#   "success": true,
#   "data": {
#     "certificate_id": "550e8400-e29b-41d4-a716-446655440000",
#     "authorization_type": "bug_bounty_platform",
#     "target": "example.com",
#     "expires_at": "2026-02-02T00:00:00"
#   }
# }

# SAVE THE certificate_id - you'll need it
```

✅ **Checkpoint 18: Authorization certificate created**

---

## FINAL VERIFICATION (5 minutes)

### Step 20: Run First Scan
**Time: 5 minutes**

```bash
# From your host machine Terminal/PowerShell

# Test OSINT scan (uses your authorization)
curl -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-email@example.com",
    "target": "example.com"
  }'

# You should see:
# {
#   "success": true,
#   "data": {
#     "scan_id": "scan-12345",
#     "target": "example.com",
#     "status": "started"
#   }
# }

# If you see error, check your authorization certificate created in Step 19
```

✅ **Checkpoint 19: First scan initiated**

---

## COMPLETION CHECK

### Step 21: Verify All Components
**Time: 2 minutes**

Run this checklist:

```bash
# In VM Terminal, run each command

# ✓ Backend running
curl http://localhost:8000/health
# Should output: {"status":"ok"}

# ✓ Database connected
PGPASSWORD=strong_password_123 psql -U k1_user -d k1_db -c "SELECT NOW();"
# Should output: current timestamp

# ✓ Redis connected
redis-cli ping
# Should output: PONG

# ✓ Frontend accessible
# Open browser and go to http://[VM_IP]:5173
# Should show Kaison K1 dashboard

# ✓ Audit logs working
journalctl -u k1-backend | tail -5
# Should show recent K1 logs

# ✓ Firewall active
sudo ufw status
# Should show: Status: active
```

✅ **ALL CHECKPOINTS COMPLETE!**

---

## QUICK REFERENCE COMMANDS

```bash
# Everything is running - here are your daily commands:

# Check status of all services
sudo systemctl status postgresql redis-server

# View backend logs
journalctl -u k1-backend -f

# View frontend logs
journalctl -u k1-frontend -f

# Stop backend (do this if you need to restart)
cd ~/kai/apps/backend
source venv/bin/activate
# Press Ctrl+C to stop

# Stop frontend
cd ~/kai/apps/frontend
# Press Ctrl+C to stop

# Restart everything
# Stop all (Ctrl+C in each terminal)
# Then run Step 15 and 16 again

# Connect to VM from host
ssh -i ~/.ssh/k1_vm_key -p 22 k1admin@[VM_IP]
```

---

## TROUBLESHOOTING

### If Backend Won't Start
```bash
# Check Python version
python3.11 --version

# Check venv is activated (shows (venv) in prompt)
source ~/kai/apps/backend/venv/bin/activate

# Check dependencies installed
pip list | grep anthropic

# If missing, reinstall:
pip install -r requirements.txt

# Check .env file
cat ~/kai/apps/backend/.env | head -5

# Check database connection
PGPASSWORD=strong_password_123 psql -U k1_user -d k1_db -c "SELECT 1;"
```

### If Frontend Won't Build
```bash
# Check Node version
node --version  # Should be v18+

# Clear npm cache
npm cache clean --force

# Remove node_modules and reinstall
cd ~/kai/apps/frontend
rm -rf node_modules package-lock.json
npm install

# Try building again
npm run build
```

### If Can't Access Dashboard
```bash
# Get VM IP
hostname -I

# Ping it from host
ping [VM_IP]

# Check if ports are listening
sudo netstat -tlnp | grep LISTEN

# Should see :8000 and :5173 in output

# Check firewall isn't blocking
sudo ufw status
```

### If Authorization Fails
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check k1_db exists
sudo -u postgres psql -l | grep k1_db

# Recreate if needed
sudo -u postgres psql
CREATE DATABASE k1_db;
GRANT ALL PRIVILEGES ON DATABASE k1_db TO k1_user;
\q
```

---

## SUCCESS! YOU'RE DONE 🎉

You now have:

✅ Ubuntu 22.04 hardened on VMware
✅ K1 backend API running on port 8000
✅ K1 frontend dashboard running on port 5173
✅ PostgreSQL database configured
✅ Redis cache configured
✅ Authorization system ready
✅ First scan tested
✅ Ready to hunt vulnerabilities

---

## NEXT STEPS (OUTSIDE THIS CHECKLIST)

1. **Create More Authorizations**
   - For different targets
   - For different bug bounty programs
   - All logged immutably

2. **Run Real Scans**
   - Use K1 tools from dashboard
   - Analyze findings
   - Create professional reports

3. **Start Bug Bounty Hunting**
   - Submit to HackerOne
   - Submit to Bugcrowd
   - Track payouts

4. **Create Daily Backups**
   - VMware snapshots
   - Database backups
   - Configuration backups

---

## TOTAL TIME ESTIMATE

| Phase | Time |
|-------|------|
| Initial Setup | 15 min |
| Security Hardening | 30 min |
| K1 Installation | 45 min |
| Configuration | 20 min |
| Start Services | 10 min |
| Verification | 10 min |
| **TOTAL** | **~2.5 hours** |

**From fresh VM to hunting bugs: 2.5 hours** ⏱️

---

**Start with Step 1. Follow in order. You've got this! 🚀**

Generated: February 2, 2025
For: First-time K1 VM setup
Status: ✅ Complete & Ready

