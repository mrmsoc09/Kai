import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
import re

class NucleiWrapper:
    def __init__(self, run_id, base_output_dir, targets, scope_enforcer, templates_path=None):
        self.run_id = run_id
        self.base_output = Path(base_output_dir)
        self.targets = targets # List of URLs/IPs to scan
        self.scope_enforcer = scope_enforcer # Function to enforce scope
        self.templates_path = templates_path # Path to custom templates or 'default'
        self.tool_output_dir = self.base_output / "raw" / "nuclei"
        self.tool_output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.base_output / "logs" / f"nuclei_{run_id}.log"

    def _log(self, message, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] [{level}] [NucleiWrapper] {message}"
        print(msg)
        with open(self.log_file, "a") as f:
            f.write(msg + "
")

    def _run_docker_tool_simulated(self, image_name, command_args, network="kai_internal", mount_local_dir=None, cap_add=None, templates_mount_path=None):
        """
        Simulates the execution of a Dockerized tool. 
        In a real scenario, this would call KaiEngine's _run_docker_tool.
        """
        self._log(f"Simulating Docker command for {image_name}: {image_name} {' '.join(command_args)}")
        self._log(f"Simulated mount_local_dir: {mount_local_dir}")
        if templates_mount_path: self._log(f"Simulated templates_mount_path: {templates_mount_path}")

        # Simulate Nuclei JSON output
        simulated_output_file = Path(mount_local_dir) / "nuclei_raw.json"
        simulated_json_content = [
            {
                "template": "generic-xss",
                "template-info": {"name": "Generic XSS", "severity": "High"},
                "matched-at": f"http://{self.targets[0]}/search?q=test<script>alert(1)</script>",
                "host": f"http://{self.targets[0]}",
                "ip": "192.168.1.10",
                "timestamp": "2026-05-06T12:00:00.000Z"
            },
            {
                "template": "info-exposure-phpinfo",
                "template-info": {"name": "PHP Info File", "severity": "Info"},
                "matched-at": f"http://{self.targets[0]}/info.php",
                "host": f"http://{self.targets[0]}",
                "ip": "192.168.1.10",
                "timestamp": "2026-05-06T12:01:00.000Z"
            },
            {
                "template": "cve-2023-xxxx",
                "template-info": {"name": "Out-of-Scope Vulnerability", "severity": "Critical"},
                "matched-at": "http://bad.evil.com/vulnerable",
                "host": "http://bad.evil.com",
                "ip": "10.0.0.5",
                "timestamp": "2026-05-06T12:02:00.000Z"
            }
        ]
        with open(simulated_output_file, "w") as f:
            json.dump(simulated_json_content, f, indent=4)
        self._log(f"Simulated output written to {simulated_output_file}")
        
        # Simulate success
        return subprocess.CompletedProcess(args=command_args, returncode=0, stdout="Simulated stdout", stderr="")

    def run(self):
        self._log(f"Running Nuclei for targets: {self.targets}")
        
        raw_out_file_name = "nuclei_raw.json"
        raw_out_path_local = self.tool_output_dir / raw_out_file_name
        container_mount_dir = Path("/app/data")
        raw_out_path_container = container_mount_dir / raw_out_file_name
        
        # Nuclei command construction
        command_args = ["-json", "-silent", "-o", str(raw_out_path_container)]
        for target in self.targets:
            command_args.extend(["-u", target])
        
        # Handle templates
        local_templates_dir = None
        container_templates_dir = None
        if self.templates_path and self.templates_path != 'default':
            local_templates_dir = Path(self.templates_path)
            container_templates_dir = Path("/app/templates") # Consistent mount point for templates
            command_args.extend(["-t", str(container_templates_dir)])
        elif self.templates_path == 'default':
            # Nuclei will use its default installed templates
            pass
        else:
            self._log("No Nuclei templates specified, using default behavior.", level="WARNING")

        try:
            self._run_docker_tool_simulated(
                image_name="kai-nuclei",
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent,
                templates_mount_path=local_templates_dir # Pass through for simulation logging
            )
            
            # Parse Nuclei JSON output
            findings = []
            with open(raw_out_path_local, "r") as f:
                nuclei_results = json.load(f)
            
            for result in nuclei_results:
                target_asset = result.get('host') or result.get('ip') or result.get('matched-at')
                
                # Enforce scope on the target_asset
                if not self.scope_enforcer(target_asset):
                    self._log(f"Nuclei finding for {target_asset} is out of scope. Skipping.", level="DEBUG")
                    continue

                findings.postpend({
                    "asset": target_asset, # Simplified for now, should link to Asset ID
                    "type": result.get('template-info', {}).get('name', 'Unknown Vulnerability'),
                    "severity": result.get('template-info', {}).get('severity', 'Info'),
                    "description": f"Nuclei detected {result.get('template-info', {}).get('name', 'a vulnerability')} at {result.get('matched-at')}",
                    "tool": "nuclei",
                    "details": result # Store full result for now
                })
            
            norm_out_path = self.base_output / "normalized" / f"nuclei_findings_{self.run_id}.json"
            with open(norm_out_path, "w") as f:
                json.dump(findings, f, indent=4)
            
            self._log(f"Nuclei scan complete. Found {len(findings)} vulnerability findings. Normalized output to {norm_out_path}")
            return findings

        except subprocess.CalledProcessError as e:
            self._log(f"Nuclei Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except json.JSONDecodeError as e:
            self._log(f"Failed to parse Nuclei JSON output: {e}", level="ERROR")
            return []
        except Exception as e:
            self._log(f"An unexpected error occurred during Nuclei run: {e}", level="ERROR")
            return []

# Example of how it would be called from KaiEngine:
# kai_instance = KaiEngine("example.com")
# nuclei_targets = ["http://example.com", "http://sub.example.com"]
# nuclei_wrapper = NucleiWrapper(
#     run_id=kai_instance.run_id,
#     base_output_dir=kai_instance.base_output,
#     targets=nuclei_targets,
#     scope_enforcer=kai_instance.enforce_scope,
#     templates_path="/path/to/custom_nuclei_templates" # or 'default'
# )
# nuclei_findings = nuclei_wrapper.run()
