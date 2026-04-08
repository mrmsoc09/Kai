#!/usr/bin/env python3
import os
import subprocess
import logging
import shutil
from pathlib import Path

# --- Configuration ---
LOG_FILE = "logs/setup_dependencies.log"
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DependencyFortress")

TOOLS = {
    "nuclei": {
        "repo": "projectdiscovery/nuclei",
        "binary": "nuclei",
        "install_type": "go",
        "version": "v3.3.0"
    },
    "subfinder": {
        "repo": "projectdiscovery/subfinder",
        "binary": "subfinder",
        "install_type": "go",
        "version": "v2.6.6"
    },
    "ffuf": {
        "repo": "ffuf/ffuf",
        "binary": "ffuf",
        "install_type": "go",
        "version": "v2.1.0"
    },
    "msfconsole": {
        "binary": "msfconsole",
        "install_type": "apt",
        "package": "metasploit-framework"
    }
}

def check_go():
    if not shutil.which("go"):
        logger.error("Go is not installed. Please install Go first.")
        return False
    return True

def install_go_tool(name, config):
    repo = config["repo"]
    logger.info(f"Installing {name} from {repo}...")
    try:
        # Attempt installation via go install
        cmd = ["go", "install", f"github.com/{repo}/v3/cmd/{name}@latest" if "projectdiscovery" in repo else f"github.com/{repo}@latest"]
        subprocess.run(cmd, check=True)
        logger.info(f"Successfully installed {name}.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install {name} via go install: {e}")
        logger.info(f"Attempting alternative binary download for {name}...")
        # Binary download logic would go here
        return False

def install_apt_tool(name, config):
    package = config["package"]
    logger.info(f"Installing {package} via apt...")
    try:
        subprocess.run(["sudo", "apt-get", "update"], check=True)
        subprocess.run(["sudo", "apt-get", "install", "-y", package], check=True)
        logger.info(f"Successfully installed {package}.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install {package} via apt: {e}")
        return False

def setup_fortress():
    logger.info("Starting K1 Dependency Fortress setup...")
    
    if not check_go():
        return

    for tool, config in TOOLS.items():
        if shutil.which(config["binary"]):
            logger.info(f"{tool} is already installed. Skipping.")
            continue

        if config["install_type"] == "go":
            install_go_tool(tool, config)
        elif config["install_type"] == "apt":
            install_apt_tool(tool, config)

    logger.info("Dependency Fortress setup complete.")

if __name__ == "__main__":
    setup_fortress()
