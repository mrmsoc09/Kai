import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
import re

class TheHarvesterWrapper:
    def __init__(self, run_id, base_output_dir, target_domain, scope_enforcer):
        self.run_id = run_id
        self.base_output = Path(base_output_dir)
        self.target = target_domain
        self.scope_enforcer = scope_enforcer # Function to enforce scope
        self.tool_output_dir = self.base_output / "raw" / "theharvester"
        self.tool_output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.base_output / "logs" / f"theharvester_{run_id}.log"

    def _log(self, message, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] [{level}] [TheHarvesterWrapper] {message}"
        print(msg)
        with open(self.log_file, "a") as f:
            f.write(msg + "
")

    def _run_docker_tool_simulated(self, image_name, command_args, network="kai_internal", mount_local_dir=None, cap_add=None):
        """
        Simulates the execution of a Dockerized tool. 
        In a real scenario, this would call KaiEngine's _run_docker_tool.
        """
        self._log(f"Simulating Docker command for {image_name}: {image_name} {' '.join(command_args)}")
        self._log(f"Simulated mount_local_dir: {mount_local_dir}")

        # Simulate tool output
        simulated_output_file = Path(mount_local_dir) / "theharvester_raw.txt"
        simulated_subdomains = [
            f"sub1.{self.target}",
            f"sub2.{self.target}",
            f"outofscope.evil.com", # Example out-of-scope
            f"sub3.{self.target}"
        ]
        with open(simulated_output_file, "w") as f:
            for sub in simulated_subdomains:
                f.write(sub + "
")
        self._log(f"Simulated output written to {simulated_output_file}")
        
        # Simulate success
        return subprocess.CompletedProcess(args=command_args, returncode=0, stdout="Simulated stdout", stderr="")

    def run(self):
        self._log(f"Running TheHarvester for target: {self.target}")
        
        raw_out_file_name = "theharvester_raw.txt"
        raw_out_path_local = self.tool_output_dir / raw_out_file_name
        container_mount_dir = Path("/app/data") # Consistent mount point inside container
        raw_out_path_container = container_mount_dir / raw_out_file_name # Path inside container

        command_args = ["-d", self.target, "-silent", "-l", "50", "-b", "all", "-f", str(raw_out_path_container)]
        
        try:
            # In actual implementation, self._run_docker_tool would be called from KaiEngine
            self._run_docker_tool_simulated(
                image_name="kai-theharvester",
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent
            )
            
            # Normalization and Scope Enforcement
            discovered_subdomains = []
            with open(raw_out_path_local, "r") as f:
                for line in f:
                    sub = line.strip()
                    if self.scope_enforcer(sub): # Enforce scope here
                        discovered_subdomains.append(sub)
            
            norm_out_path = self.base_output / "normalized" / f"theharvester_subdomains_{self.run_id}.json"
            with open(norm_out_path, "w") as f:
                json.dump({"source": "theharvester", "data": discovered_subdomains}, f, indent=4)
            
            self._log(f"Found {len(discovered_subdomains)} in-scope subdomains with TheHarvester. Normalized output to {norm_out_path}")
            return discovered_subdomains

        except subprocess.CalledProcessError as e:
            self._log(f"TheHarvester Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except Exception as e:
            self._log(f"An unexpected error occurred during TheHarvester run: {e}", level="ERROR")
            return []

# Example of how it would be called from KaiEngine (once kai_master.py is writable):
# Assuming kai_master.py has self.enforce_scope and self.base_output properly set.
# kai_instance = KaiEngine("example.com")
# harvester_wrapper = TheHarvesterWrapper(
#     run_id=kai_instance.run_id,
#     base_output_dir=kai_instance.base_output,
#     target_domain=kai_instance.target,
#     scope_enforcer=kai_instance.enforce_scope
# )
# subdomains = harvester_wrapper.run()
