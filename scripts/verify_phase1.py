#!/usr/bin/env python3
"""
Phase 1 Verification Script
Checks if environment setup is complete and all systems are ready
"""

import sys
import os
from pathlib import Path

# Load .env file
from dotenv import load_dotenv
load_dotenv('.env')

# Colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
NC = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}")
    print(f"{text:^60}")
    print(f"{'='*60}{NC}\n")

def print_success(text):
    print(f"{GREEN}[✓]{NC} {text}")

def print_error(text):
    print(f"{RED}[✗]{NC} {text}")

def print_warning(text):
    print(f"{YELLOW}[!]{NC} {text}")

def print_info(text):
    print(f"{BLUE}[i]{NC} {text}")

def check_python_version():
    print_header("1. Python Version Check")

    version = sys.version_info
    if version.major >= 3 and version.minor >= 11:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} - Need Python 3.11+")
        return False

def check_environment_file():
    print_header("2. Environment File Check")

    env_file = Path(".env")
    if not env_file.exists():
        print_error(".env file not found")
        return False

    print_success(".env file exists")

    # Check for required variables in loaded env
    required_vars = [
        "DATABASE_URL",
        "REDIS_URL",
        "K1_DEV_TOKEN",
    ]

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print_success(f"  {var} = {value[:50]}...")
        else:
            missing.append(var)

    if missing:
        print_warning(f"  Missing or empty: {', '.join(missing)}")
        return False

    return True

def check_imports():
    print_header("3. Python Imports Check")

    modules = [
        ("fastapi", "FastAPI"),
        ("pydantic", "Pydantic"),
        ("sqlalchemy", "SQLAlchemy"),
        ("redis", "Redis"),
        ("networkx", "NetworkX"),
        ("yaml", "PyYAML"),
        ("jinja2", "Jinja2"),
        ("uvicorn", "Uvicorn"),
        ("httpx", "httpx"),
    ]

    all_good = True
    for module, name in modules:
        try:
            __import__(module)
            print_success(f"{name} available")
        except ImportError:
            print_error(f"{name} NOT installed")
            all_good = False

    return all_good

def check_directories():
    print_header("4. Directory Structure Check")

    required_dirs = [
        "artifacts/logs",
        "artifacts/evidence",
        "artifacts/dork_runs",
        "artifacts/reports",
        "artifacts/submissions",
        "data/dorks/google",
        "data/nuclei_templates",
        "apps/backend/src",
        "apps/frontend",
        "modules",
        "configs",
    ]

    all_exist = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print_success(f"  {dir_path}/")
        else:
            print_warning(f"  {dir_path}/ - Creating...")
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    return True

def check_configuration_files():
    print_header("5. Configuration Files Check")

    config_files = [
        "configs/policies.yaml",
        "configs/knowledge.yaml",
        "configs/provider_registry.yaml",
    ]

    all_exist = True
    for config_file in config_files:
        if Path(config_file).exists():
            print_success(f"  {config_file}")
        else:
            print_warning(f"  {config_file} - Not found")
            all_exist = False

    return all_exist

def check_module_imports():
    print_header("6. Application Module Imports Check")

    sys.path.insert(0, os.getcwd())

    # Try importing main routers
    try:
        from apps.backend.src import main
        print_success("apps.backend.src.main imports successfully")
    except Exception as e:
        print_error(f"apps.backend.src.main import failed: {e}")
        return False

    # Try importing core modules
    try:
        from apps.backend.src.core import auth
        print_success("apps.backend.src.core.auth imports successfully")
    except Exception as e:
        print_error(f"apps.backend.src.core.auth import failed: {e}")
        return False

    try:
        from apps.backend.src.routers import dorks
        print_success("apps.backend.src.routers.dorks imports successfully")
    except Exception as e:
        print_error(f"apps.backend.src.routers.dorks import failed: {e}")
        return False

    return True

def check_database_config():
    print_header("7. Database Configuration Check")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print_error("DATABASE_URL not set in .env")
        return False

    print_success(f"DATABASE_URL configured: {database_url.split('@')[0]}@...")

    if "postgresql" in database_url:
        print_success("PostgreSQL database configured")
    else:
        print_warning(f"Unknown database type in: {database_url}")

    return True

def check_redis_config():
    print_header("8. Redis Configuration Check")

    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        print_error("REDIS_URL not set in .env")
        return False

    print_success(f"REDIS_URL configured: {redis_url}")

    return True

def check_llm_config():
    print_header("9. LLM Configuration Check")

    llm_provider = os.getenv("LLM_PROVIDER", "anthropic")
    print_info(f"LLM Provider: {llm_provider}")

    if llm_provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if api_key and api_key != "sk-ant-xxx-replace-with-your-key":
            print_success("Anthropic API key configured")
        else:
            print_warning("Anthropic API key not set - patch engine will fail")
            print_info("Get your key from: https://console.anthropic.com/")
            return False

    return True

def check_cors_config():
    print_header("10. CORS Configuration Check")

    cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")

    if not cors_origins:
        print_error("CORS_ALLOWED_ORIGINS not configured")
        return False

    origins = [o.strip() for o in cors_origins.split(",")]
    print_success(f"CORS configured for {len(origins)} origin(s):")
    for origin in origins:
        print_info(f"  {origin}")

    if "http://localhost:8081" not in origins:
        print_warning("Frontend origin (localhost:8081) not in CORS list")

    return True

def main():
    print("\n")
    print(f"{BLUE}╔══════════════════════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║{NC}         K1 PHASE 1: ENVIRONMENT VERIFICATION            {BLUE}║{NC}")
    print(f"{BLUE}╚══════════════════════════════════════════════════════════╝{NC}\n")

    checks = [
        ("Python Version", check_python_version),
        ("Environment File", check_environment_file),
        ("Python Imports", check_imports),
        ("Directory Structure", check_directories),
        ("Configuration Files", check_configuration_files),
        ("Module Imports", check_module_imports),
        ("Database Config", check_database_config),
        ("Redis Config", check_redis_config),
        ("LLM Config", check_llm_config),
        ("CORS Config", check_cors_config),
    ]

    results = {}
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print_error(f"Check failed with exception: {e}")
            results[check_name] = False

    # Summary
    print_header("VERIFICATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for check_name, result in results.items():
        status = f"{GREEN}PASS{NC}" if result else f"{RED}FAIL{NC}"
        print(f"  {check_name:.<40} {status}")

    print(f"\n  Total: {passed}/{total} checks passed")

    if passed == total:
        print(f"\n{GREEN}{'='*60}")
        print(f"{'✓ PHASE 1 ENVIRONMENT READY':^60}")
        print(f"{'='*60}{NC}\n")
        print("Next steps:")
        print("  1. If using Docker: docker-compose -f docker-compose.dev.yml up -d")
        print("  2. If using local setup:")
        print("     - Ensure PostgreSQL is running on localhost:5432")
        print("     - Ensure Redis is running on localhost:6379")
        print("     - Then run: python3 apps/backend/src/main.py")
        print()
        return 0
    else:
        print(f"\n{RED}{'='*60}")
        print(f"{'✗ SOME CHECKS FAILED':^60}")
        print(f"{'='*60}{NC}\n")
        print("Fix the failed checks and run this script again.")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
