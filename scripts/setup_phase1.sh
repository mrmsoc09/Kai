#!/bin/bash
# K1 Phase 1: Environment Setup Script
# This script sets up your K1 environment for local development

set -e  # Exit on error

echo "=================================================="
echo "K1 Phase 1: Environment Setup"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
print_status "Working directory: $PROJECT_ROOT"

# ==================== CHECK PREREQUISITES ====================
echo ""
echo "Step 1: Checking prerequisites..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Please install Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
print_status "Python 3 found: $PYTHON_VERSION"

# Check pip
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 not found. Please install pip."
    exit 1
fi

print_status "pip3 found"

# ==================== CREATE VIRTUAL ENVIRONMENT ====================
echo ""
echo "Step 2: Setting up Python virtual environment..."
echo ""

if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
else
    print_warning "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
print_status "Virtual environment activated"

# Upgrade pip, setuptools, wheel
print_status "Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel >/dev/null 2>&1

# ==================== INSTALL DEPENDENCIES ====================
echo ""
echo "Step 3: Installing Python dependencies..."
echo ""

print_status "Installing requirements from requirements.txt..."
pip install -r requirements.txt

print_status "All dependencies installed successfully"

# ==================== SETUP DIRECTORIES ====================
echo ""
echo "Step 4: Creating necessary directories..."
echo ""

mkdir -p artifacts/logs
mkdir -p artifacts/evidence
mkdir -p artifacts/dork_runs
mkdir -p artifacts/reports
mkdir -p artifacts/submissions
mkdir -p data/dorks/google
mkdir -p data/nuclei_templates

print_status "Directories created"

# ==================== CHECK DATABASE ====================
echo ""
echo "Step 5: Database configuration check..."
echo ""

if ! command -v psql &> /dev/null; then
    print_warning "PostgreSQL client not found. You may need to set up PostgreSQL separately."
    print_warning "For Docker: Run 'docker-compose up -d postgres'"
    print_warning "For local: Install PostgreSQL and update DATABASE_URL in .env"
else
    print_status "PostgreSQL client found"
fi

# ==================== CHECK REDIS ====================
echo ""
echo "Step 6: Redis configuration check..."
echo ""

if ! command -v redis-cli &> /dev/null; then
    print_warning "Redis client not found. You may need to set up Redis separately."
    print_warning "For Docker: Run 'docker-compose up -d redis'"
    print_warning "For local: Install Redis and ensure it's running"
else
    print_status "Redis client found"
fi

# ==================== VERIFY IMPORTS ====================
echo ""
echo "Step 7: Verifying Python imports..."
echo ""

python3 << 'EOF'
import sys
print("Checking core imports...")

try:
    import fastapi
    print("  ✓ fastapi")
except ImportError as e:
    print(f"  ✗ fastapi: {e}")
    sys.exit(1)

try:
    import pydantic
    print("  ✓ pydantic")
except ImportError as e:
    print(f"  ✗ pydantic: {e}")
    sys.exit(1)

try:
    import sqlalchemy
    print("  ✓ sqlalchemy")
except ImportError as e:
    print(f"  ✗ sqlalchemy: {e}")
    sys.exit(1)

try:
    import redis
    print("  ✓ redis")
except ImportError as e:
    print(f"  ✗ redis: {e}")
    sys.exit(1)

try:
    import networkx
    print("  ✓ networkx")
except ImportError as e:
    print(f"  ✗ networkx: {e}")
    sys.exit(1)

try:
    import yaml
    print("  ✓ yaml")
except ImportError as e:
    print(f"  ✗ yaml: {e}")
    sys.exit(1)

print("\nAll core imports successful!")
EOF

if [ $? -ne 0 ]; then
    print_error "Import verification failed"
    exit 1
fi

print_status "All imports verified"

# ==================== CHECK .ENV ====================
echo ""
echo "Step 8: Checking .env configuration..."
echo ""

if [ -f ".env" ]; then
    print_status ".env file found"
    if grep -q "ANTHROPIC_API_KEY=sk-ant-xxx" .env; then
        print_warning ".env contains placeholder API key - remember to add your real Anthropic API key"
    fi
else
    print_error ".env file not found"
    exit 1
fi

# ==================== FINAL CHECK ====================
echo ""
echo "Step 9: Environment summary..."
echo ""

echo "Project Root: $PROJECT_ROOT"
echo "Python: $(python3 --version)"
echo "Pip: $(pip --version)"
echo "Virtual Environment: $(which python3)"
echo "Requirements File: $([ -f requirements.txt ] && echo '✓' || echo '✗')"
echo "Directories Created: $([ -d artifacts ] && echo '✓' || echo '✗')"
echo ".env Configuration: $([ -f .env ] && echo '✓' || echo '✗')"

# ==================== SUCCESS ====================
echo ""
echo "=================================================="
print_status "Phase 1: Environment Setup COMPLETE!"
echo "=================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your .env file:"
echo "   - Add your ANTHROPIC_API_KEY"
echo "   - Verify DATABASE_URL and REDIS_URL"
echo ""
echo "2. Set up PostgreSQL and Redis:"
echo "   Option A (Docker):"
echo "     docker-compose up -d postgres redis"
echo ""
echo "   Option B (Local):"
echo "     - Install PostgreSQL and create database 'k1'"
echo "     - Install Redis"
echo ""
echo "3. Initialize the database:"
echo "   export PYTHONPATH=/home/user23/kai/Kaison_Latest_Build"
echo "   python3 -m alembic upgrade heads"
echo ""
echo "4. Test backend startup:"
echo "   export PYTHONPATH=/home/user23/kai/Kaison_Latest_Build"
echo "   python3 apps/backend/src/main.py"
echo ""
echo "5. Test frontend (in another terminal):"
echo "   cd apps/frontend"
echo "   npm install"
echo "   npm run dev"
echo ""
echo "For Docker setup:"
echo "   docker-compose up -d"
echo "   docker-compose logs -f"
echo ""
