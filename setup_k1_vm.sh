#!/bin/bash

################################################################################
# Kaison K1 - Automated VMware Ubuntu 22.04 Setup Script
# 
# Purpose: Automate K1 installation from fresh Ubuntu 22.04 VM
# Usage: ./setup_k1_vm.sh
# 
# This script handles:
# - System security hardening
# - K1 installation and configuration
# - Database setup (PostgreSQL + Redis)
# - Service initialization
# - Verification and testing
#
# Version: 1.0
# Created: February 2, 2025
################################################################################

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# State file to track progress
STATE_FILE="$HOME/.k1_setup_state"

################################################################################
# UTILITY FUNCTIONS
################################################################################

print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}\n"
}

print_step() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

prompt_user() {
    local prompt_text=$1
    local default_value=$2
    local input
    
    if [ -n "$default_value" ]; then
        echo -n -e "${YELLOW}?${NC} $prompt_text [default: $default_value]: "
    else
        echo -n -e "${YELLOW}?${NC} $prompt_text: "
    fi
    
    read input
    
    if [ -z "$input" ] && [ -n "$default_value" ]; then
        echo "$default_value"
    else
        echo "$input"
    fi
}

prompt_password() {
    local prompt_text=$1
    local password
    local password_confirm
    
    while true; do
        echo -n -e "${YELLOW}?${NC} $prompt_text: "
        read -s password
        echo
        
        echo -n -e "${YELLOW}?${NC} Confirm password: "
        read -s password_confirm
        echo
        
        if [ "$password" == "$password_confirm" ]; then
            echo "$password"
            break
        else
            print_error "Passwords don't match. Try again."
        fi
    done
}

prompt_yes_no() {
    local prompt_text=$1
    local response
    
    while true; do
        echo -n -e "${YELLOW}?${NC} $prompt_text (y/n): "
        read response
        
        if [[ "$response" =~ ^[Yy]$ ]]; then
            return 0
        elif [[ "$response" =~ ^[Nn]$ ]]; then
            return 1
        else
            print_warning "Please enter 'y' or 'n'"
        fi
    done
}

save_state() {
    local step=$1
    echo "$step" >> "$STATE_FILE"
}

step_completed() {
    local step=$1
    if grep -q "^$step$" "$STATE_FILE" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

################################################################################
# STEP 0: PRE-FLIGHT CHECKS
################################################################################

preflight_check() {
    print_header "PRE-FLIGHT CHECKS"
    
    # Check if running Ubuntu 22.04
    if ! grep -q "22.04" /etc/lsb-release 2>/dev/null; then
        print_warning "This script is designed for Ubuntu 22.04"
        if ! prompt_yes_no "Continue anyway?"; then
            print_error "Aborting setup"
            exit 1
        fi
    fi
    
    # Check internet connection
    if ! ping -c 1 8.8.8.8 &> /dev/null; then
        print_error "No internet connection detected"
        print_info "Please connect to internet before continuing"
        exit 1
    fi
    print_step "Internet connection verified"
    
    # Check if running as regular user (not root)
    if [ "$EUID" -eq 0 ]; then
        print_error "Please run as regular user, not root"
        exit 1
    fi
    print_step "User permissions verified"
    
    # Check available disk space (need at least 50GB)
    available_space=$(df /home | tail -1 | awk '{print $4}')
    if [ "$available_space" -lt 52428800 ]; then  # 50GB in KB
        print_error "Insufficient disk space (need 50GB)"
        exit 1
    fi
    print_step "Disk space verified ($(numfmt --to=iec $available_space)B available)"
}

################################################################################
# STEP 1: INITIAL SETUP
################################################################################

system_update() {
    if step_completed "system_update"; then
        print_step "System already updated - skipping"
        return
    fi
    
    print_header "STEP 1: SYSTEM UPDATE & INITIAL SETUP"
    
    print_info "Updating system packages..."
    sudo apt update
    sudo apt upgrade -y
    sudo apt dist-upgrade -y
    sudo apt autoremove -y
    
    print_step "System updated successfully"
    save_state "system_update"
}

################################################################################
# STEP 2: SSH KEY SETUP
################################################################################

ssh_key_setup() {
    if step_completed "ssh_key_setup"; then
        print_step "SSH already configured - skipping"
        return
    fi
    
    print_header "STEP 2: SSH KEY CONFIGURATION"
    
    # Create .ssh directory
    mkdir -p ~/.ssh
    chmod 700 ~/.ssh
    
    print_info "SSH key setup:"
    print_info "1. If you have an existing SSH key on your host machine,"
    print_info "   copy the public key content and paste it below"
    print_info "2. If you don't have one, generate it on your host:"
    print_info "   ssh-keygen -t ed25519 -C 'k1-vm-key' -f ~/.ssh/k1_vm_key"
    echo
    
    if prompt_yes_no "Do you have an SSH public key ready to paste?"; then
        print_info "Paste your public key (Ctrl+D to finish):"
        cat >> ~/.ssh/authorized_keys
        chmod 600 ~/.ssh/authorized_keys
        print_step "SSH public key added"
    else
        print_warning "SSH key not configured - password authentication will be used"
        print_info "Recommendation: Generate SSH key on your host machine for better security"
    fi
    
    sudo systemctl enable ssh
    sudo systemctl start ssh
    
    print_step "SSH configured successfully"
    print_info "Your VM IP: $(hostname -I | awk '{print $1}')"
    save_state "ssh_key_setup"
}

################################################################################
# STEP 3: FIREWALL SETUP
################################################################################

firewall_setup() {
    if step_completed "firewall_setup"; then
        print_step "Firewall already configured - skipping"
        return
    fi
    
    print_header "STEP 3: FIREWALL CONFIGURATION"
    
    print_info "Installing UFW firewall..."
    sudo apt install -y ufw
    
    # Configure firewall
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow 22/tcp  # SSH
    sudo ufw enable
    
    print_step "Firewall configured"
    print_info "Firewall status:"
    sudo ufw status
    
    save_state "firewall_setup"
}

################################################################################
# STEP 4: KERNEL HARDENING
################################################################################

kernel_hardening() {
    if step_completed "kernel_hardening"; then
        print_step "Kernel already hardened - skipping"
        return
    fi
    
    print_header "STEP 4: KERNEL HARDENING WITH APPARMOR"
    
    print_info "Applying kernel security parameters..."
    
    # Edit GRUB
    sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash apparmor=1 security=apparmor"/' /etc/default/grub
    sudo update-grub
    
    print_step "Kernel hardening applied"
    print_warning "System needs to reboot for changes to take effect"
    print_info "Continuing setup without reboot (will prompt at the end)"
    
    save_state "kernel_hardening"
}

################################################################################
# STEP 5: SECURITY TOOLS
################################################################################

install_security_tools() {
    if step_completed "install_security_tools"; then
        print_step "Security tools already installed - skipping"
        return
    fi
    
    print_header "STEP 5: INSTALLING SECURITY TOOLS"
    
    print_info "Installing security packages..."
    sudo apt install -y ufw fail2ban auditd audispd-plugins
    
    # Start audit daemon
    sudo systemctl enable auditd
    sudo systemctl start auditd
    
    print_step "Security tools installed"
    save_state "install_security_tools"
}

################################################################################
# STEP 6: INSTALL K1 DEPENDENCIES
################################################################################

install_dependencies() {
    if step_completed "install_dependencies"; then
        print_step "Dependencies already installed - skipping"
        return
    fi
    
    print_header "STEP 6: INSTALLING K1 DEPENDENCIES"
    
    print_info "Installing Python 3.11..."
    sudo apt install -y python3.11 python3.11-venv python3.11-dev
    
    print_info "Installing Node.js..."
    sudo apt install -y nodejs npm
    
    print_info "Installing utilities..."
    sudo apt install -y git curl wget
    
    # Verify versions
    print_step "Dependency versions:"
    echo "  Python: $(python3.11 --version)"
    echo "  Node: $(node --version)"
    echo "  npm: $(npm --version)"
    
    save_state "install_dependencies"
}

################################################################################
# STEP 7: INSTALL DATABASE & CACHE
################################################################################

install_databases() {
    if step_completed "install_databases"; then
        print_step "Databases already installed - skipping"
        return
    fi
    
    print_header "STEP 7: INSTALLING POSTGRESQL & REDIS"
    
    print_info "Installing PostgreSQL..."
    sudo apt install -y postgresql postgresql-contrib
    sudo systemctl enable postgresql
    sudo systemctl start postgresql
    
    print_info "Installing Redis..."
    sudo apt install -y redis-server
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
    
    print_step "PostgreSQL and Redis installed"
    print_info "PostgreSQL status: $(sudo systemctl is-active postgresql)"
    print_info "Redis status: $(sudo systemctl is-active redis-server)"
    
    save_state "install_databases"
}

################################################################################
# STEP 8: CLONE K1 REPOSITORY
################################################################################

clone_k1_repo() {
    if step_completed "clone_k1_repo"; then
        print_step "K1 repository already cloned - skipping"
        return
    fi
    
    print_header "STEP 8: CLONING K1 REPOSITORY"
    
    K1_DIR="$HOME/kai"
    
    if [ -d "$K1_DIR" ]; then
        print_warning "K1 directory already exists at $K1_DIR"
        if prompt_yes_no "Update existing repository?"; then
            cd "$K1_DIR"
            git pull origin main
        fi
    else
        print_info "Cloning K1 from GitHub..."
        git clone https://github.com/mrmsoc09/Kaison_Latest_Build.git "$K1_DIR"
    fi
    
    cd "$K1_DIR"
    print_step "K1 repository ready"
    print_info "Latest commit: $(git log --oneline -1)"
    
    save_state "clone_k1_repo"
}

################################################################################
# STEP 9: SETUP BACKEND
################################################################################

setup_backend() {
    if step_completed "setup_backend"; then
        print_step "Backend already configured - skipping"
        return
    fi
    
    print_header "STEP 9: SETTING UP K1 BACKEND"
    
    K1_DIR="$HOME/kai"
    BACKEND_DIR="$K1_DIR/apps/backend"
    
    cd "$BACKEND_DIR"
    
    print_info "Creating Python virtual environment..."
    python3.11 -m venv venv
    source venv/bin/activate
    
    print_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel
    
    print_info "Installing Python dependencies..."
    print_info "(This may take 2-3 minutes...)"
    pip install -r requirements.txt
    
    # Verify installation
    if python -c "import anthropic" 2>/dev/null; then
        print_step "Anthropic SDK installed"
    else
        print_error "Failed to install Anthropic SDK"
        exit 1
    fi
    
    print_step "Backend installed successfully"
    save_state "setup_backend"
}

################################################################################
# STEP 10: SETUP FRONTEND
################################################################################

setup_frontend() {
    if step_completed "setup_frontend"; then
        print_step "Frontend already configured - skipping"
        return
    fi
    
    print_header "STEP 10: SETTING UP K1 FRONTEND"
    
    K1_DIR="$HOME/kai"
    FRONTEND_DIR="$K1_DIR/apps/frontend"
    
    cd "$FRONTEND_DIR"
    
    print_info "Installing Node dependencies..."
    npm install
    
    print_info "Building frontend..."
    npm run build
    
    if [ -d "dist" ]; then
        print_step "Frontend built successfully"
    else
        print_error "Frontend build failed"
        exit 1
    fi
    
    save_state "setup_frontend"
}

################################################################################
# STEP 11: CONFIGURE ENVIRONMENT VARIABLES
################################################################################

configure_env() {
    if step_completed "configure_env"; then
        print_step "Environment already configured - skipping"
        return
    fi
    
    print_header "STEP 11: CONFIGURING ENVIRONMENT VARIABLES"
    
    K1_DIR="$HOME/kai"
    ENV_FILE="$K1_DIR/apps/backend/.env"
    
    print_info "K1 requires several configuration values."
    print_warning "You need an Anthropic API key to proceed."
    print_info "Get it from: https://console.anthropic.com"
    echo
    
    # Collect information
    ANTHROPIC_API_KEY=$(prompt_user "Enter your Anthropic API key" "")
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        print_error "Anthropic API key is required"
        exit 1
    fi
    
    DB_PASSWORD=$(prompt_password "Enter PostgreSQL password for k1_user")
    REDIS_PASSWORD=$(prompt_password "Enter Redis password")
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    USER_EMAIL=$(prompt_user "Enter your email address (for logging)" "your-email@example.com")
    
    # Create .env file
    cat > "$ENV_FILE" << ENVEOF
# Core Settings
ENVIRONMENT=production
DEBUG_MODE=false
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://k1_user:${DB_PASSWORD}@localhost:5432/k1_db
DATABASE_POOL_SIZE=20

# Cache
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=${REDIS_PASSWORD}

# LLM Providers
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# Security
SECRET_KEY=${SECRET_KEY}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Email & Logging
USER_EMAIL=${USER_EMAIL}
LOG_FILE=/var/log/k1/backend.log
LOG_LEVEL=info
ENVEOF
    
    chmod 600 "$ENV_FILE"
    
    print_step "Environment variables configured"
    print_warning "Keep your .env file secure - it contains sensitive information"
    
    save_state "configure_env"
}

################################################################################
# STEP 12: SETUP POSTGRESQL DATABASE
################################################################################

setup_postgresql() {
    if step_completed "setup_postgresql"; then
        print_step "PostgreSQL database already configured - skipping"
        return
    fi
    
    print_header "STEP 12: SETTING UP POSTGRESQL DATABASE"
    
    # Get password from .env
    DB_PASSWORD=$(grep "DATABASE_URL" "$HOME/kai/apps/backend/.env" | grep -oP '(?<=:)[^@]*(?=@)' | tail -1)
    
    print_info "Creating PostgreSQL database and user..."
    
    sudo -u postgres psql << SQLEOF
CREATE DATABASE k1_db;
CREATE USER k1_user WITH PASSWORD '$DB_PASSWORD';
ALTER ROLE k1_user SET client_encoding TO 'utf8';
ALTER ROLE k1_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE k1_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE k1_db TO k1_user;
SQLEOF
    
    # Verify
    if PGPASSWORD="$DB_PASSWORD" psql -U k1_user -d k1_db -c "SELECT 1;" -h localhost &>/dev/null; then
        print_step "PostgreSQL database created and verified"
    else
        print_error "Failed to verify PostgreSQL connection"
        exit 1
    fi
    
    save_state "setup_postgresql"
}

################################################################################
# STEP 13: CONFIGURE FIREWALL FOR K1
################################################################################

configure_firewall_k1() {
    if step_completed "configure_firewall_k1"; then
        print_step "K1 firewall rules already configured - skipping"
        return
    fi
    
    print_header "STEP 13: CONFIGURING FIREWALL FOR K1 SERVICES"
    
    # Allow K1 services (internal only)
    sudo ufw allow from 127.0.0.1 to any port 8000   # Backend API
    sudo ufw allow from 127.0.0.1 to any port 5173   # Frontend
    sudo ufw allow from 127.0.0.1 to any port 5432   # PostgreSQL
    sudo ufw allow from 127.0.0.1 to any port 6379   # Redis
    
    print_step "K1 firewall rules configured"
    print_info "Current firewall rules:"
    sudo ufw show added
    
    save_state "configure_firewall_k1"
}

################################################################################
# STEP 14: CREATE LOGGING DIRECTORY
################################################################################

setup_logging() {
    if step_completed "setup_logging"; then
        print_step "Logging directory already configured - skipping"
        return
    fi
    
    print_header "STEP 14: SETTING UP LOGGING"
    
    print_info "Creating logging directory..."
    sudo mkdir -p /var/log/k1
    sudo chown $USER:$USER /var/log/k1
    chmod 755 /var/log/k1
    
    print_step "Logging directory configured"
    
    save_state "setup_logging"
}

################################################################################
# STEP 15: FINAL VERIFICATION
################################################################################

final_verification() {
    print_header "FINAL VERIFICATION"
    
    print_info "Checking all components..."
    
    # Check Python
    if python3.11 --version &>/dev/null; then
        print_step "Python 3.11: OK"
    else
        print_error "Python 3.11: FAILED"
        exit 1
    fi
    
    # Check Node
    if node --version &>/dev/null; then
        print_step "Node.js: OK"
    else
        print_error "Node.js: FAILED"
        exit 1
    fi
    
    # Check PostgreSQL
    if sudo systemctl is-active --quiet postgresql; then
        print_step "PostgreSQL: OK"
    else
        print_error "PostgreSQL: FAILED"
        exit 1
    fi
    
    # Check Redis
    if sudo systemctl is-active --quiet redis-server; then
        print_step "Redis: OK"
    else
        print_error "Redis: FAILED"
        exit 1
    fi
    
    # Check K1 repo
    if [ -d "$HOME/kai" ]; then
        print_step "K1 Repository: OK"
    else
        print_error "K1 Repository: FAILED"
        exit 1
    fi
    
    # Check backend venv
    if [ -d "$HOME/kai/apps/backend/venv" ]; then
        print_step "Backend Virtual Environment: OK"
    else
        print_error "Backend Virtual Environment: FAILED"
        exit 1
    fi
    
    # Check frontend dist
    if [ -d "$HOME/kai/apps/frontend/dist" ]; then
        print_step "Frontend Build: OK"
    else
        print_error "Frontend Build: FAILED"
        exit 1
    fi
    
    print_step "All components verified successfully!"
}

################################################################################
# STEP 16: DISPLAY NEXT STEPS
################################################################################

display_next_steps() {
    print_header "SETUP COMPLETE! 🎉"
    
    echo -e "${GREEN}K1 is now installed and ready to run!${NC}\n"
    
    echo -e "${BLUE}NEXT STEPS:${NC}"
    echo "1. Review the README documentation"
    echo "2. Read FIRST_VM_BOOT_CHECKLIST.md for manual startup instructions"
    echo "3. Start K1 services:"
    echo ""
    echo -e "${YELLOW}   # Terminal 1 - Backend:${NC}"
    echo "   cd ~/kai/apps/backend"
    echo "   source venv/bin/activate"
    echo "   python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000"
    echo ""
    echo -e "${YELLOW}   # Terminal 2 - Frontend:${NC}"
    echo "   cd ~/kai/apps/frontend"
    echo "   npm run dev"
    echo ""
    echo -e "${YELLOW}   # Access Dashboard:${NC}"
    echo "   Browser: http://localhost:5173"
    echo ""
    echo -e "${BLUE}IMPORTANT SECURITY REMINDERS:${NC}"
    echo "✓ Keep your .env file secure (contains API keys)"
    echo "✓ Use SSH key-based authentication (not passwords)"
    echo "✓ Keep your Anthropic API key confidential"
    echo "✓ Review audit logs regularly: /var/log/k1/"
    echo "✓ Make regular backups of your database"
    echo ""
    echo -e "${BLUE}VM INFORMATION:${NC}"
    echo "  IP Address: $(hostname -I | awk '{print $1}')"
    echo "  Hostname: $(hostname)"
    echo "  K1 Directory: $HOME/kai"
    echo ""
    
    if prompt_yes_no "Would you like to start the services now?"; then
        start_services
    fi
}

################################################################################
# START SERVICES (OPTIONAL)
################################################################################

start_services() {
    print_header "STARTING K1 SERVICES"
    
    K1_DIR="$HOME/kai"
    
    echo -e "${BLUE}Backend will start in a new terminal...${NC}"
    echo "Run this command in Terminal 1:"
    echo "cd $K1_DIR/apps/backend && source venv/bin/activate && python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000"
    echo ""
    echo -e "${BLUE}Frontend will start in a new terminal...${NC}"
    echo "Run this command in Terminal 2:"
    echo "cd $K1_DIR/apps/frontend && npm run dev"
    echo ""
    echo "Press Enter to continue..."
    read
}

################################################################################
# MAIN EXECUTION
################################################################################

main() {
    print_header "Kaison K1 - Automated Setup Script"
    
    echo "This script will:"
    echo "  ✓ Harden Ubuntu system security"
    echo "  ✓ Install K1 dependencies"
    echo "  ✓ Setup PostgreSQL and Redis"
    echo "  ✓ Configure K1 backend and frontend"
    echo "  ✓ Prepare services for startup"
    echo ""
    
    if ! prompt_yes_no "Continue with K1 setup?"; then
        print_info "Setup cancelled"
        exit 0
    fi
    
    echo ""
    
    # Run all setup steps
    preflight_check
    system_update
    ssh_key_setup
    firewall_setup
    kernel_hardening
    install_security_tools
    install_dependencies
    install_databases
    clone_k1_repo
    setup_backend
    setup_frontend
    configure_env
    setup_postgresql
    configure_firewall_k1
    setup_logging
    final_verification
    display_next_steps
    
    print_header "🎉 SETUP COMPLETED SUCCESSFULLY!"
    
    print_info "Setup state saved to: $STATE_FILE"
    print_info "To resume setup later, run this script again"
    print_info "To reset progress, delete: $STATE_FILE"
}

# Run main function
main "$@"
