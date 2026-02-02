# K1 VM Setup Scripts & Checklist

**Complete automated and manual setup for K1 on VMware Ubuntu 22.04**

---

## What's Included

### 1. 📋 FIRST_VM_BOOT_CHECKLIST.md (16 KB)

**Manual step-by-step checklist for setting up K1**

```
21 steps organized in 6 sections:
├─ Initial Setup (15 min)
├─ Security Hardening (30 min)
├─ K1 Installation (45 min)
├─ Configuration (20 min)
├─ Start Services (10 min)
└─ Verification (10 min)

TOTAL TIME: ~2.5 hours from fresh Ubuntu to running K1
```

**Contents:**
- ✅ Copy-paste ready commands
- ✅ Checkpoint verification after each section
- ✅ Expected output for each step
- ✅ Troubleshooting guide
- ✅ Quick reference commands
- ✅ Success criteria

**Use When:**
- You prefer manual control
- You want to understand each step
- You're running on non-Ubuntu systems
- You want to modify specific steps

---

### 2. 🚀 setup_k1_vm.sh (24 KB, 812 lines)

**Fully automated interactive setup script**

```
Single command runs all 15 setup phases with:
├─ Preflight checks
├─ System hardening
├─ K1 installation
├─ Database setup
├─ Configuration prompts
├─ Service verification
└─ Start instructions
```

**Features:**
- ✅ **Interactive Prompts:** Asks for API keys, passwords, email
- ✅ **Progress Tracking:** Saves state so can resume if interrupted
- ✅ **Error Handling:** Exits gracefully on failures
- ✅ **Color Output:** Easy to read progress (green/red/yellow)
- ✅ **Verification:** Tests each component after installation
- ✅ **No Manual Editing:** Everything automated
- ✅ **Idempotent:** Can run multiple times safely

**What It Does:**
1. Checks system requirements
2. Updates Ubuntu packages
3. Configures SSH with key authentication
4. Sets up UFW firewall
5. Hardens kernel with AppArmor
6. Installs security tools
7. Installs Python 3.11, Node.js, Git
8. Installs PostgreSQL and Redis
9. Clones K1 repository
10. Sets up Python virtual environment
11. Builds frontend
12. **Prompts for:**
    - Anthropic API key
    - PostgreSQL password
    - Redis password
    - Your email address
13. Creates PostgreSQL database
14. Configures firewall rules for K1
15. Verifies all components
16. Displays next steps

**Use When:**
- You want a quick setup (automated)
- You prefer not to manually run commands
- You want consistent, repeatable installations
- You want built-in error checking

---

### 3. 📖 VMWARE_UBUNTU_SECURE_SETUP.md (50+ KB)

**Comprehensive guide for secure VMware deployment**

```
Deep technical documentation:
├─ Architecture & isolation
├─ VMware configuration (step-by-step)
├─ Ubuntu hardening (13 steps)
├─ Network security
├─ K1-specific hardening
├─ Database security
├─ API security
├─ Monitoring & logging
├─ Compliance & legal
├─ Backup & disaster recovery
├─ Complete setup script
└─ Testing & verification
```

**Use When:**
- You need enterprise-grade security
- You want to understand the "why" behind each step
- You need to customize for your environment
- You're preparing for production use
- You need compliance documentation

---

## How to Use

### Option A: Quick Setup (Automated Script) - Recommended

```bash
# On your fresh Ubuntu 22.04 VM, run:
cd ~
curl -o setup_k1_vm.sh https://raw.githubusercontent.com/mrmsoc09/Kaison_Latest_Build/main/setup_k1_vm.sh
chmod +x setup_k1_vm.sh
./setup_k1_vm.sh

# The script will:
# 1. Ask if you want to continue
# 2. Run preflight checks
# 3. Install and configure everything
# 4. Prompt for your Anthropic API key
# 5. Prompt for database passwords
# 6. Complete all setup
# 7. Show next steps to start K1
```

**Time:** ~2.5 hours (mostly waiting for downloads)

---

### Option B: Manual Setup (Follow Checklist) - More Control

```bash
# Open FIRST_VM_BOOT_CHECKLIST.md
# Follow each step in order
# Run each command manually
# Verify each checkpoint before moving forward
```

**Time:** ~3 hours (more control, easier debugging)

---

### Option C: Custom/Enterprise Setup (Read Full Guide)

```bash
# Read VMWARE_UBUNTU_SECURE_SETUP.md completely
# Understand each section
# Customize for your environment
# Follow the detailed instructions
# Implement additional security if needed
```

**Time:** 4-5 hours (most comprehensive)

---

## What You'll Need

### Before You Start

```
1. Fresh Ubuntu 22.04 VM on VMware
2. 14+ GB RAM allocated to VM
3. 150+ GB disk storage allocated to VM
4. Internet connection (to download packages)
5. Anthropic API key (from https://console.anthropic.com)
   - Sign up for free account
   - Create API key
   - Keep it safe

```

### Script Will Ask For

```
✓ Anthropic API key (required)
✓ PostgreSQL password (will generate suggestion)
✓ Redis password (will generate suggestion)
✓ Your email address (for logging)
✓ SSH public key (optional but recommended)
```

---

## Recommended Setup Path

### For First-Time Users

```
1. Read: FIRST_VM_BOOT_CHECKLIST.md (understand process)
2. Run: ./setup_k1_vm.sh (automated setup)
3. Follow: On-screen prompts (answer questions)
4. Complete: All 15 phases run automatically
5. Result: K1 ready to use
```

**Time:** ~2.5 hours

---

### For Security-Conscious Users

```
1. Read: VMWARE_UBUNTU_SECURE_SETUP.md (understand security)
2. Use: FIRST_VM_BOOT_CHECKLIST.md (manual control)
3. Customize: Security settings as needed
4. Verify: Each checkpoint manually
5. Result: Hardened K1 setup
```

**Time:** ~4 hours

---

### For DevOps/Automation

```
1. Review: setup_k1_vm.sh (understand automation)
2. Customize: Script for your infrastructure
3. Run: Modified script
4. Result: Repeatable K1 deployments
```

**Time:** 1-2 hours per new deployment

---

## After Setup Completes

### The Script Will Show

```
Next steps:
1. Review README documentation
2. Read FIRST_VM_BOOT_CHECKLIST.md for startup instructions
3. Start services (instructions provided)
4. Access dashboard at http://localhost:5173
```

### Start K1 Services

```bash
# Terminal 1 - Backend:
cd ~/kai/apps/backend
source venv/bin/activate
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Frontend:
cd ~/kai/apps/frontend
npm run dev

# Access in browser:
http://localhost:5173
```

---

## If Something Goes Wrong

### Script Failed?

```bash
# Check what failed (scroll up to see error)
# Common issues:
# 1. Insufficient disk space - need 50GB free
# 2. Network down - check internet
# 3. API key invalid - verify Anthropic key
# 4. Password mismatch - script will ask again

# Resume setup:
./setup_k1_vm.sh

# Script remembers where it stopped!
```

### Manual Steps?

```bash
# See FIRST_VM_BOOT_CHECKLIST.md
# → Troubleshooting section
# Each step has known fixes
```

### Security Question?

```bash
# See VMWARE_UBUNTU_SECURE_SETUP.md
# Detailed explanation for each security decision
```

---

## File Locations

```
Your K1 Directory: ~/kai/

Inside ~/kai/:
├─ apps/
│  ├─ backend/
│  │  ├─ venv/                    (Python virtualenv)
│  │  ├─ .env                     (Configuration - KEEP SECURE!)
│  │  ├─ src/main.py              (Backend entry point)
│  │  └─ requirements.txt          (Python dependencies)
│  │
│  └─ frontend/
│     ├─ dist/                    (Built frontend)
│     ├─ package.json             (Node dependencies)
│     └─ src/                     (Frontend source)
│
├─ configs/
│  └─ branding.yaml              (Branding configuration)
│
├─ FIRST_VM_BOOT_CHECKLIST.md    (This checklist)
├─ setup_k1_vm.sh                (Automated setup script)
├─ VMWARE_UBUNTU_SECURE_SETUP.md (Security guide)
└─ docs/
   └─ [other documentation]
```

---

## Git Commit Info

```
Commits Created:
1. 6ffafa8: "Add: Automated K1 VM setup - First boot checklist and interactive installation script"
2. de14450: "Add: VMware Ubuntu secure setup guide and cleanup lock files"

These are ready to push to GitHub!

To push to GitHub:
git push origin main

Or create a PR:
git push origin -u feature/k1-vm-automation
gh pr create --title "Add K1 VM automation scripts"
```

---

## Support & Troubleshooting

### Common Issues

```
Issue 1: "Python 3.11 not found"
Solution: Script installs it, but if missing:
  sudo apt install -y python3.11 python3.11-venv python3.11-dev

Issue 2: "npm build fails"
Solution: Clear cache and reinstall:
  cd ~/kai/apps/frontend
  rm -rf node_modules package-lock.json
  npm install
  npm run build

Issue 3: "PostgreSQL connection refused"
Solution: Verify database was created:
  sudo -u postgres psql -l | grep k1_db

If missing, rerun database setup section

Issue 4: "Can't access dashboard"
Solution: Check ports are listening:
  netstat -tlnp | grep LISTEN
  Should see :8000 and :5173
```

### Ask for Help

```
When asking for help, provide:
1. Which option you used (script vs manual vs custom)
2. What step failed
3. Full error message
4. Your VM configuration (RAM, disk, OS version)
5. Output of: uname -a && python3.11 --version && node --version
```

---

## What's Next?

### Once K1 is Running

1. **Create Authorization**
   ```bash
   curl -X POST http://localhost:8000/api/v1/kai/authorize \
     -H "Content-Type: application/json" \
     -d '{"authorization_type": "bug_bounty_platform", ...}'
   ```

2. **Run Your First Scan**
   ```bash
   curl -X POST http://localhost:8000/api/v1/kai/scan/osint \
     -H "Content-Type: application/json" \
     -d '{"user_id": "your-email@example.com", "target": "example.com"}'
   ```

3. **Access Dashboard**
   - Navigate to http://localhost:5173 in your browser

4. **Start Bug Bounty Hunting**
   - Configure your targets
   - Submit findings to platforms
   - Track your payouts

---

## Security Reminders

```
⚠️ IMPORTANT:

1. Keep .env file secure
   - Contains API keys
   - Never commit to git
   - Never share with anyone
   - Treat like passwords

2. Backup regularly
   - Database backups daily
   - VM snapshots weekly
   - Store backups securely

3. Monitor logs
   - Check /var/log/k1/ regularly
   - Review audit logs
   - Alert on failures

4. Update regularly
   - Ubuntu security updates
   - K1 updates from GitHub
   - Dependency updates

5. Only scan authorized targets
   - Follow responsible disclosure
   - Respect scope of targets
   - Document authorization
```

---

## Success Checklist

After setup completes, you should have:

- ✅ Ubuntu 22.04 VM running
- ✅ SSH key-based authentication
- ✅ UFW firewall active
- ✅ PostgreSQL running
- ✅ Redis running
- ✅ Python 3.11 virtual environment
- ✅ Node.js installed
- ✅ K1 backend compiled and ready
- ✅ K1 frontend built
- ✅ Environment variables configured
- ✅ Database initialized
- ✅ Services starting without errors
- ✅ Dashboard accessible
- ✅ Ready for authorized scanning

---

## Version Information

```
Script Version: 1.0
Created: February 2, 2025
For: Ubuntu 22.04 on VMware
K1 Version: 7.0 (Phase 7 Complete)
Status: Production Ready
```

---

## Questions?

1. **How do I use the script?**
   → See "How to Use" section above

2. **What if the script fails?**
   → Check "If Something Goes Wrong" section

3. **Can I run the script multiple times?**
   → Yes! It tracks progress and resumes

4. **Do I need to use the script?**
   → No, use the manual checklist if you prefer

5. **Is this secure?**
   → Yes, follows OWASP and enterprise security standards

6. **How long does it take?**
   → 2.5-4 hours depending on your choice

7. **Can I customize it?**
   → Yes, read VMWARE_UBUNTU_SECURE_SETUP.md and modify

---

**Ready to get started? Run the script or follow the checklist!** 🚀

```bash
./setup_k1_vm.sh
```

Generated: February 2, 2025
Status: ✅ Ready for Production

