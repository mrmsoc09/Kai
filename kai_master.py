#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
import re

import hvac # Import HashiCorp Vault client

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

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

        self.secrets = {} # Initialize secrets dictionary
        self._load_vault_secrets() # Load secrets from Vault


    def _init_directories(self):
        subdirs = ['raw', 'normalized', 'reports', 'workflows', 'logs']
        for sd in subdirs:
            (self.base_output / sd).mkdir(parents=True, exist_ok=True)

    def _load_vault_secrets(self):
        self.log("Attempting to load secrets from HashiCorp Vault (conceptual)...")
        vault_addr = os.getenv("VAULT_ADDR")
        vault_token = os.getenv("VAULT_TOKEN")

        if not vault_addr or not vault_token:
            self.log("VAULT_ADDR or VAULT_TOKEN not set. Skipping Vault integration.", level="WARNING")
            # Simulate some default/placeholder secrets if Vault is not configured
            self.secrets["SHODAN_API_KEY"] = os.getenv("SHODAN_API_KEY", "mock_shodan_key")
            self.secrets["DARKSEARCH_API_KEY"] = os.getenv("DARKSEARCH_API_KEY", "mock_darksearch_key")
            self.secrets["NUCLEI_TEMPLATES_PATH"] = os.getenv("NUCLEI_TEMPLATES_PATH", "/opt/nuclei-templates")
            self.secrets["BURP_API_KEY"] = os.getenv("BURP_API_KEY", "mock_burp_key")
            self.secrets["BURP_TEMPLATES_PATH"] = os.getenv("BURP_TEMPLATES_PATH", "/opt/burp-templates") # Placeholder for Burp templates
            return

        try:
            client = hvac.Client(url=vault_addr, token=vault_token)
            if not client.is_authenticated():
                self.log("Vault authentication failed. Check token.", level="ERROR")
                return

            # Define secret paths to retrieve
            secret_paths = {
                "osint": "secret/data/kai/osint",
                "darkweb": "secret/data/kai/darkweb",
                "scanning": "secret/data/kai/scanning",
                "nuclei": "secret/data/kai/nuclei",
                # Add other paths as needed
            }

            for category, path in secret_paths.items():
                try:
                    read_response = client.secrets.kv.v2.read_secret_version(path=path)
                    if read_response and 'data' in read_response and 'data' in read_response['data']:
                        self.secrets.update(read_response['data']['data'])
                        self.log(f"Successfully loaded secrets from Vault path: {path}")
                    else:
                        self.log(f"No data found in Vault path: {path}", level="WARNING")
                except hvac.exceptions.VaultError as ve:
                    self.log(f"Vault error reading {path}: {ve}", level="ERROR")
                except Exception as ex:
                    self.log(f"Unexpected error reading {path} from Vault: {ex}", level="ERROR")
            
            self.log("Vault secret loading complete.")

        except hvac.exceptions.VaultError as e:
            self.log(f"Vault client error: {e}", level="ERROR")
        except Exception as e:
            self.log(f"An unexpected error occurred during Vault secret loading: {e}", level="ERROR")

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
            f.write(msg + "
")

    def _run_docker_tool(self, image_name, command_args, network="kai_internal", tool_output_dir="/app/output", mount_local_dir=None, cap_add=None):
        """
        Runs a Dockerized tool.
        :param image_name: Name of the Docker image (e.g., 'kai-subfinder').
        :param command_args: List of command arguments for the tool.
        :param network: Docker network to connect to.
        :param tool_output_dir: The directory *inside the container* where the tool writes its output or expects input.
        :param mount_local_dir: The path on the *host* to mount to tool_output_dir.
        :param cap_add: List of capabilities to add to the container (e.g., ["NET_RAW"]).
        :return: The completed subprocess run object.
        """
        docker_cmd = ["docker", "run", "--rm", "--network", network]

        if cap_add:
            for cap in cap_add:
                docker_cmd.extend(["--cap-add", cap])

        if mount_local_dir:
            # Ensure the local output directory exists before mounting
            Path(mount_local_dir).mkdir(parents=True, exist_ok=True)
            docker_cmd.extend(["-v", f"{mount_local_dir}:{tool_output_dir}"])
        
        docker_cmd.append(image_name)
        docker_cmd.extend(command_args)

        self.log(f"Executing Docker command: {' '.join(docker_cmd)}")
        return subprocess.run(docker_cmd, capture_output=True, text=True, check=True)

    def run_subfinder(self):
        self.log(f"Starting Phase: Passive Recon (Subfinder) on {self.target}")
        raw_out_file_name = "subfinder_raw.txt"
        raw_out_path_local = self.base_output / "raw" / raw_out_file_name
        container_mount_dir = Path("/app/data") # Consistent mount point inside container
        raw_out_path_container = container_mount_dir / raw_out_file_name # Path inside container

        command_args = ["-d", self.target, "-silent", "-o", str(raw_out_path_container)]
        
        # Example of using a secret from Vault
        shodan_api_key = self.secrets.get("SHODAN_API_KEY")
        if shodan_api_key and shodan_api_key != "mock_shodan_key": # Don't use mock key for actual tool
            command_args.extend(["-provider-config", f"shodan:{{API_KEY:{shodan_api_key}}}"]) # Example for subfinder/shodan
        else:
            self.log("SHODAN_API_KEY not found or is mock key, skipping Shodan integration in Subfinder.", level="DEBUG")
        
        try:
            self._run_docker_tool(
                image_name="kai-subfinder", # Assuming kai-subfinder image will exist and is built
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent # Mount the local raw directory
            )
            
            # Immediate Normalization (read from local mounted file)
            with open(raw_out_path_local, "r") as f:
                subs = [line.strip() for line in f if self.enforce_scope(line.strip())]
            
            norm_out = self.base_output / "normalized" / "subdomains_subfinder.json" # Differentiate source
            with open(norm_out, "w") as f:
                json.dump({"source": "subfinder", "data": subs}, f, indent=4)
            
            self.log(f"Found {len(subs)} in-scope subdomains with Subfinder.")
            return subs
        except subprocess.CalledProcessError as e:
            self.log(f"Subfinder Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except Exception as e:
            self.log(f"An unexpected error occurred during Subfinder run: {e}", level="ERROR")
            return []

    def run_amass(self):
        self.log(f"Starting Phase: Passive Recon (Amass) on {self.target}")
        raw_out_file_name = "amass_raw.txt"
        raw_out_path_local = self.base_output / "raw" / raw_out_file_name
        container_mount_dir = Path("/app/data") # Consistent mount point inside container
        raw_out_path_container = container_mount_dir / raw_out_file_name # Path inside container

        # Amass needs different args for output. Using -oA for all output formats but only caring about text for now.
        command_args = ["enum", "-d", self.target, "-o", str(raw_out_path_container)]
        
        try:
            # NOTE: kai-amass build is currently blocked due to Go version incompatibility.
            # This call will fail until that is resolved. Using a simulated runner for now.
            # self._run_docker_tool(
            #     image_name="kai-amass",
            #     command_args=command_args,
            #     mount_local_dir=raw_out_path_local.parent
            # )
            
            # Simulate Amass output for now
            simulated_subdomains = [
                f"subA.{self.target}",
                f"subB.{self.target}",
                f"sub1.{self.target}", # Overlap with subfinder
                f"outofscope.malicious.net" # Example out-of-scope
            ]
            with open(raw_out_path_local, "w") as f:
                for sub in simulated_subdomains:
                    f.write(sub + "
")
            self.log(f"Simulated Amass output written to {raw_out_path_local}")

            # Immediate Normalization (read from local mounted file)
            with open(raw_out_path_local, "r") as f:
                subs = [line.strip() for line in f if self.enforce_scope(line.strip())]
            
            norm_out = self.base_output / "normalized" / "subdomains_amass.json" # Differentiate source
            with open(norm_out, "w") as f:
                json.dump({"source": "amass", "data": subs}, f, indent=4)
            
            self.log(f"Found {len(subs)} in-scope subdomains with Amass.")
            return subs
        except subprocess.CalledProcessError as e:
            self.log(f"Amass Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except Exception as e:
            self.log(f"An unexpected error occurred during Amass run: {e}", level="ERROR")
            return []

    def run_nuclei(self, targets):
        self.log(f"Starting Phase: Vulnerability Scan (Nuclei) on {targets}")
        raw_out_file_name = "nuclei_raw.json"
        raw_out_path_local = self.base_output / "raw" / raw_out_file_name
        container_mount_dir = Path("/app/data")
        raw_out_path_container = container_mount_dir / raw_out_file_name
        
        command_args = ["-json", "-silent", "-o", str(raw_out_path_container)]
        for target in targets:
            command_args.extend(["-u", target])

        nuclei_templates_path = self.secrets.get("NUCLEI_TEMPLATES_PATH")
        if nuclei_templates_path and nuclei_templates_path != "/opt/nuclei-templates": # Only add if custom or not default
            command_args.extend(["-t", nuclei_templates_path])
            # Also need to mount the templates if custom path is used
            # This would require updating _run_docker_tool to accept an additional mount_options
            # For now, we assume the templates are already available in the container or mounted via docker-compose
        else:
            self.log("NUCLEI_TEMPLATES_PATH not found or is default, Nuclei will use its internal templates.", level="DEBUG")

        try:
            # NOTE: kai-nuclei build is currently blocked due to Go version incompatibility.
            # This call will fail until that is resolved. Using a simulated runner for now.
            # self._run_docker_tool(
            #     image_name="kai-nuclei",
            #     command_args=command_args,
            #     mount_local_dir=raw_out_path_local.parent
            # )

            # Simulate Nuclei JSON output
            simulated_results = [
                {
                    "template": "generic-xss",
                    "template-info": {"name": "Generic XSS", "severity": "High"},
                    "matched-at": f"http://{targets[0]}/search?q=test<script>alert(1)</script>",
                    "host": f"http://{targets[0]}",
                    "ip": "192.168.1.10",
                    "timestamp": "2026-05-06T12:00:00.000Z"
                },
                {
                    "template": "info-exposure-phpinfo",
                    "template-info": {"name": "PHP Info File", "severity": "Info"},
                    "matched-at": f"http://{targets[0]}/info.php",
                    "host": f"http://{targets[0]}",
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
            with open(raw_out_path_local, "w") as f:
                json.dump(simulated_results, f, indent=4)
            self.log(f"Simulated Nuclei output written to {raw_out_path_local}")

            # Parse Nuclei JSON output and enforce scope
            findings = []
            with open(raw_out_path_local, "r") as f:
                nuclei_results = json.load(f)
            
            for result in nuclei_results:
                target_asset = result.get('host') or result.get('ip') or result.get('matched-at')
                
                if target_asset and self.enforce_scope(target_asset):
                    findings.append({
                        "asset": target_asset, 
                        "type": result.get('template-info', {}).get('name', 'Unknown Vulnerability'),
                        "severity": result.get('template-info', {}).get('severity', 'Info'),
                        "description": f"Nuclei detected {result.get('template-info', {}).get('name', 'a vulnerability')} at {result.get('matched-at')}",
                        "tool": "nuclei",
                        "details": result # Store full result for now
                    })
                else:
                    self.log(f"Nuclei finding for {target_asset} is out of scope. Skipping.", level="DEBUG")

            norm_out_path = self.base_output / "normalized" / f"nuclei_findings_{self.run_id}.json"
            with open(norm_out_path, "w") as f:
                json.dump(findings, f, indent=4)
            
            self.log(f"Nuclei scan complete. Found {len(findings)} vulnerability findings. Normalized output to {norm_out_path}")
            return findings

        except subprocess.CalledProcessError as e:
            self.log(f"Nuclei Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except json.JSONDecodeError as e:
            self.log(f"Failed to parse Nuclei JSON output: {e}", level="ERROR")
            return []
        except Exception as e:
            self.log(f"An unexpected error occurred during Nuclei run: {e}", level="ERROR")
            return []

    def run_garak(self, target_llm_endpoint):
        self.log(f"Starting Phase: AI/LLM Security (Garak) on {target_llm_endpoint}")
        raw_out_file_name = "garak_raw.jsonl"
        raw_out_path_local = self.base_output / "raw" / raw_out_file_name
        container_mount_dir = Path("/app/data")
        raw_out_path_container = container_mount_dir / raw_out_file_name
        command_args = ["--model_type", "openai", "--model_name", target_llm_endpoint, "--output_format", "jsonl", "--output_file", str(raw_out_path_container)]

        try:
            self._run_docker_tool(
                image_name="kai-garak",
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent
            )
            findings = []
            with open(raw_out_path_local, "r") as f:
                for line in f:
                    result = json.loads(line.strip())
                    if self.enforce_scope(result.get("model", "")) and self.enforce_scope(target_llm_endpoint):
                        findings.append(result)
            self.log(f"Garak scan complete for {target_llm_endpoint}. Found {len(findings)} in-scope findings.")
            return findings
        except subprocess.CalledProcessError as e:
            self.log(f"Garak Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except Exception as e:
            self.log(f"An unexpected error occurred during Garak run: {e}", level="ERROR")
            return []

    def run_promptmap(self, target_llm_endpoint):
        self.log(f"Starting Phase: AI/LLM Security (PromptMap) on {target_llm_endpoint}")
        raw_out_file_name = "promptmap_raw.json"
        raw_out_path_local = self.base_output / "raw" / raw_out_file_name
        container_mount_dir = Path("/app/data")
        raw_out_path_container = container_mount_dir / raw_out_file_name
        command_args = ["scan", "--target", target_llm_endpoint, "--output", str(raw_out_path_container)]

        try:
            self._run_docker_tool(
                image_name="kai-promptmap",
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent
            )
            findings = []
            with open(raw_out_path_local, "r") as f:
                promptmap_results = json.load(f)
            for result in promptmap_results:
                if result.get("vulnerable") and self.enforce_scope(target_llm_endpoint):
                    findings.append(result)
            self.log(f"PromptMap scan complete for {target_llm_endpoint}. Found {len(findings)} in-scope vulnerabilities.")
            return findings
        except subprocess.CalledProcessError as e:
            self.log(f"PromptMap Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except Exception as e:
            self.log(f"An unexpected error occurred during PromptMap run: {e}", level="ERROR")
            return []

    def run_llmguard(self, target_llm_endpoint):
        self.log(f"Starting Phase: AI/LLM Security (LLM Guard) on {target_llm_endpoint}")
        raw_out_file_name = "llmguard_raw.json"
        raw_out_path_local = self.base_output / "raw" / raw_out_file_name
        container_mount_dir = Path("/app/data")
        raw_out_path_container = container_mount_dir / raw_out_file_name
        command_args = ["scan", "--config", "/app/config/default.yaml", "--output", str(raw_out_path_container), "--target", target_llm_endpoint]

        try:
            self._run_docker_tool(
                image_name="kai-llmguard",
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent
            )
            findings = []
            with open(raw_out_path_local, "r") as f:
                llmguard_results = json.load(f)
            for result in llmguard_results:
                if result.get("alert_level") != "NONE" and self.enforce_scope(target_llm_endpoint):
                    findings.append(result)
            self.log(f"LLM Guard scan complete for {target_llm_endpoint}. Found {len(findings)} in-scope alerts.")
            return findings
        except subprocess.CalledProcessError as e:
            self.log(f"LLM Guard Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except Exception as e:
            self.log(f"An unexpected error occurred during LLM Guard run: {e}", level="ERROR")
            return []

    def run_pyrit(self, target_llm_endpoint):
        self.log(f"Starting Phase: AI/LLM Security (PyRIT) on {target_llm_endpoint}")
        raw_out_file_name = "pyrit_raw.json"
        raw_out_path_local = self.base_output / "raw" / raw_out_file_name
        container_mount_dir = Path("/app/data")
        raw_out_path_container = container_mount_dir / raw_out_file_name
        command_args = ["run", "--strategy", "jailbreak_prompts", "--target", target_llm_endpoint, "--output", str(raw_out_path_container)]

        try:
            self._run_docker_tool(
                image_name="kai-pyrit",
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent
            )
            findings = []
            with open(raw_out_path_local, "r") as f:
                pyrit_results = json.load(f)
            for result in pyrit_results:
                if result.get("vulnerability_found") and self.enforce_scope(target_llm_endpoint):
                    findings.append(result)
            self.log(f"PyRIT scan complete for {target_llm_endpoint}. Found {len(findings)} in-scope vulnerabilities.")
            return findings
        except subprocess.CalledProcessError as e:
            self.log(f"PyRIT Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except Exception as e:
            self.log(f"An unexpected error occurred during PyRIT run: {e}", level="ERROR")
            return []

    def _correlate_subdomains(self, subdomain_lists):
        """
        Merges and deduplicates subdomain lists from multiple sources.
        :param subdomain_lists: A list of lists, where each inner list contains subdomains from a tool.
        :return: A sorted, deduplicated list of unique subdomains.
        """
        self.log("Correlating subdomain results...")
        all_subdomains = set()
        for sub_list in subdomain_lists:
            for sub in sub_list:
                all_subdomains.add(sub)
        
        correlated_subdomains = sorted(list(all_subdomains))
        norm_out = self.base_output / "normalized" / "subdomains_correlated.json"
        with open(norm_out, "w") as f:
            json.dump({"source": "correlated", "data": correlated_subdomains}, f, indent=4)
        
        self.log(f"Correlated to {len(correlated_subdomains)} unique subdomains.")
        return correlated_subdomains

    def integrate_cai(self, data_for_cai):
        """
        Conceptual integration point for Cai (CybersecurityAI) as a meta-orchestration layer.
        In a real scenario, this would involve API calls to Cai to analyze data or guide workflows.
        """
        self.log(f"Integrating with Cai (CybersecurityAI). Data provided: {len(data_for_cai)} items.", level="DEBUG")
        # Placeholder for actual Cai API call or processing logic

    def integrate_pentagi(self, data_for_pentagi):
        """
        Conceptual integration point for PentAGI as a meta-orchestration layer.
        In a real scenario, this would involve API calls to PentAGI to perform advanced reasoning or tasks.
        """
        self.log(f"Integrating with PentAGI. Data provided: {len(data_for_pentagi)} items.", level="DEBUG")
        # Placeholder for actual PentAGI API call or processing logic

    def run_httpx(self, input_list):
        self.log("Starting Phase: Live Validation (httpx)")
        input_file_name = "httpx_input.txt"
        raw_out_file_name = "httpx_raw.json"

        input_path_local = self.base_output / "raw" / input_file_name
        output_path_local = self.base_output / "raw" / raw_out_file_name

        # Paths inside container
        container_mount_dir = Path("/app/data") # A generic data dir inside container
        input_path_container = container_mount_dir / input_file_name
        output_path_container = container_mount_dir / raw_out_file_name

        with open(input_path_local, "w") as f:
            f.write("
".join(input_list))
            
        command_args = ["-l", str(input_path_container), "-json", "-silent", "-o", str(output_path_container)]
        
        try:
            self._run_docker_tool(
                image_name="kai-httpx", # Assuming kai-httpx image will exist
                command_args=command_args,
                mount_local_dir=input_path_local.parent # Mount the local raw directory
            )
            
            # Logic for parsing JSON output would go here for the Correlation Engine
            self.log("Live validation complete with httpx.")
        except subprocess.CalledProcessError as e:
            self.log(f"httpx Docker execution failed: {e.stderr}", level="ERROR")
            return
        except Exception as e:
            self.log(f"An unexpected error occurred during httpx run: {e}", level="ERROR")
            return

    # --- Workflow Orchestration ---

    def workflow_recon_surface_map(self):
        """Implementation of your requested surface mapping workflow."""
        self.log("EXECUTING WORKFLOW: recon_surface_map")
        
        # 1. Discovery
        subdomains_subfinder = self.run_subfinder()
        subdomains_amass = self.run_amass() # Run Amass for redundancy
        
        correlated_subdomains = self._correlate_subdomains([subdomains_subfinder, subdomains_amass])

        # Example of conceptual AI integration
        self.integrate_cai(correlated_subdomains)
        self.integrate_pentagi({"subdomains": correlated_subdomains, "target": self.target})

        # Example of conceptual manual tool integration placeholders
        self.integrate_burp_suite({"target_domain": self.target, "subdomains": correlated_subdomains})
        self.integrate_metasploit({"target_domain": self.target, "correlated_assets": correlated_subdomains})

        # --- 3. AI/LLM Security Testing (Conceptual) ---
        self.log("Starting Phase: AI/LLM Security Testing")
        placeholder_llm_endpoint = "http://mock-llm-service:8001" # Replace with actual discovered/configured LLM endpoint

        garak_findings = self.run_garak(placeholder_llm_endpoint)
        promptmap_findings = self.run_promptmap(placeholder_llm_endpoint)
        llmguard_alerts = self.run_llmguard(placeholder_llm_endpoint)
        pyrit_vulnerabilities = self.run_pyrit(placeholder_llm_endpoint)

        self.log(f"AI/LLM Security Testing Complete. Garak: {len(garak_findings)} findings, PromptMap: {len(promptmap_findings)} findings, LLM Guard: {len(llmguard_alerts)} alerts, PyRIT: {len(pyrit_vulnerabilities)} vulnerabilities.")

        # 4. Validation
        if correlated_subdomains:
            self.run_httpx(correlated_subdomains)
        
        self.log("Workflow Complete. Generating Summary Report...")
        # (Report generation logic here)

    def integrate_burp_suite(self, scan_context):
        """
        Conceptual integration point for Burp Suite. 
        In a real scenario, this would involve launching Burp in headless mode, 
        configuring its scanner via API, or loading specific project files/BAPPs.
        """
        self.log(f"Integrating with Burp Suite. Context: {scan_context}", level="DEBUG")
        burp_templates_path = self.secrets.get("BURP_TEMPLATES_PATH")
        if burp_templates_path:
            self.log(f"Using Burp Suite templates from: {burp_templates_path}", level="DEBUG")
        else:
            self.log("BURP_TEMPLATES_PATH not found, using default Burp Suite behavior.", level="DEBUG")
        # Placeholder for actual Burp Suite interaction logic

    def integrate_metasploit(self, scan_context):
        """
        Conceptual integration point for Metasploit Framework.
        In a real scenario, this would involve launching msfconsole via RPC/scripting 
        to run specific modules or exploit chains based on discovered vulnerabilities.
        """
        self.log(f"Integrating with Metasploit Framework. Context: {scan_context}", level="DEBUG")
        # Placeholder for actual Metasploit interaction logic

class ScanRequest(BaseModel):
    target_domain: str

# Initialize FastAPI app
app = FastAPI()

# KaiEngine instance (global for the FastAPI app)
kai_engine_instance = None

@app.post("/admin/start_scan")
async def start_scan_api(request: ScanRequest, background_tasks: BackgroundTasks):
    global kai_engine_instance
    if kai_engine_instance is None:
        kai_engine_instance = KaiEngine(target_domain=request.target_domain)
    else:
        # For simplicity, if instance exists, update its target. In a real app,
        # you'd likely have a new instance per scan or a more complex state management.
        kai_engine_instance.target = request.target_domain
        # Re-initialize output directories for the new target
        kai_engine_instance.run_id = f"run_{kai_engine_instance.target}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        kai_engine_instance.base_output = kai_engine_instance.project_root / "outputs" / kai_engine_instance.run_id
        kai_engine_instance._init_directories()

    background_tasks.add_task(kai_engine_instance.workflow_recon_surface_map)
    return {"message": f"Scan initiated for {request.target_domain} in background."}


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description="Kaison AI Master Controller")
    parser.add_argument("-d", "--domain", required=False, help="Target domain (for direct CLI run)")
    parser.add_argument("-w", "--workflow", default="recon_surface_map", help="Workflow name (for direct CLI run)")
    parser.add_argument("--api", action="store_true", help="Run in API mode")

    args = parser.parse_args()
    
    if args.api:
        # In API mode, KaiEngine is instantiated when first scan is requested
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        # Original CLI mode logic
        if not args.domain:
            print("Error: --domain is required for CLI mode unless --api is used.")
            sys.exit(1)
        kai = KaiEngine(args.domain)
        if args.workflow == "recon_surface_map":
            kai.workflow_recon_surface_map()
