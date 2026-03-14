#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
import re

class KaiEngine:
    """
    The central intelligence for Kaison AI. 
    Manages workflows, enforces scope, and normalizes tool outputs.
    """
    def __init__(self, target_domain, config_path=None):
        self.target = target_domain
        self.start_time = datetime.now()
        self.project_root = Path(__file__).parent.resolve()
        
        # Load Scope & Config
        self.scope = self._load_scope(config_path)
        
        # Initialize Output Hierarchy
        self.run_id = f"run_{self.target}_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        self.base_output = self.project_root / "outputs" / self.run_id
        self._init_directories()

    def _init_directories(self):
        subdirs = ['raw', 'normalized', 'reports', 'workflows', 'logs']
        for sd in subdirs:
            (self.base_output / sd).mkdir(parents=True, exist_ok=True)

    def _load_scope(self, path):
        # Default to strict: only the target domain and its subdomains
        return {
            "allowlist": [re.compile(rf"(.*\.)?{re.escape(self.target)}$")],
            "denylist": []
        }

    def enforce_scope(self, item):
        """Standardized check for all discovered assets."""
        for pattern in self.scope["denylist"]:
            if pattern.search(item): return False
        for pattern in self.scope["allowlist"]:
            if pattern.search(item): return True
        return False

    def log(self, message, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] [{level}] {message}"
        print(msg)
        with open(self.base_output / "logs" / "engine.log", "a") as f:
            f.write(msg + "\n")

    # --- Tool Registry Wrappers ---

    def run_subfinder(self):
        self.log(f"Starting Phase: Passive Recon (Subfinder) on {self.target}")
        raw_out = self.base_output / "raw" / "subfinder_raw.txt"
        
        # Execute binary directly from OS path
        cmd = ["subfinder", "-d", self.target, "-silent", "-o", str(raw_out)]
        subprocess.run(cmd, check=True)
        
        # Immediate Normalization
        with open(raw_out, "r") as f:
            subs = [line.strip() for line in f if self.enforce_scope(line.strip())]
        
        norm_out = self.base_output / "normalized" / "subdomains.json"
        with open(norm_out, "w") as f:
            json.dump({"source": "subfinder", "data": subs}, f, indent=4)
        
        self.log(f"Found {len(subs)} in-scope subdomains.")
        return subs

    def run_httpx(self, input_list):
        self.log("Starting Phase: Live Validation (httpx)")
        input_file = self.base_output / "raw" / "httpx_input.txt"
        with open(input_file, "w") as f:
            f.write("\n".join(input_list))
            
        raw_out = self.base_output / "raw" / "httpx_raw.json"
        cmd = ["httpx", "-l", str(input_file), "-json", "-silent", "-o", str(raw_out)]
        subprocess.run(cmd, check=True)
        
        # Logic for parsing JSON output would go here for the Correlation Engine
        self.log("Live validation complete.")

    # --- Workflow Orchestration ---

    def workflow_recon_surface_map(self):
        """Implementation of your requested surface mapping workflow."""
        self.log("EXECUTING WORKFLOW: recon_surface_map")
        
        # 1. Discovery
        subdomains = self.run_subfinder()
        
        # 2. Validation
        if subdomains:
            self.run_httpx(subdomains)
        
        self.log("Workflow Complete. Generating Summary Report...")
        # (Report generation logic here)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaison AI Master Controller")
    parser.add_argument("-d", "--domain", required=True, help="Target domain")
    parser.add_argument("-w", "--workflow", default="recon_surface_map", help="Workflow name")
    
    args = parser.parse_args()
    
    kai = KaiEngine(args.domain)
    if args.workflow == "recon_surface_map":
        kai.workflow_recon_surface_map()
