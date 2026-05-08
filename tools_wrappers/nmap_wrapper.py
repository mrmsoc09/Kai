import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
import re
import xml.etree.ElementTree as ET

class NmapWrapper:
    def __init__(self, run_id, base_output_dir, target_scope, scope_enforcer):
        self.run_id = run_id
        self.base_output = Path(base_output_dir)
        self.target_scope = target_scope # List of IPs/domains to scan
        self.scope_enforcer = scope_enforcer # Function to enforce scope
        self.tool_output_dir = self.base_output / "raw" / "nmap"
        self.tool_output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.base_output / "logs" / f"nmap_{run_id}.log"

    def _log(self, message, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] [{level}] [NmapWrapper] {message}"
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

        # Simulate Nmap XML output
        simulated_output_file = Path(mount_local_dir) / "nmap_raw.xml"
        simulated_xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<nmaprun scanner="nmap" args="nmap -sV example.com" start="1678886400" version="7.93">
<host starttime="1678886400" endtime="1678886410">
<address addr="192.168.1.1" addrtype="ipv4"/>
<hostnames><hostname name="host1.example.com" type="user"/></hostnames>
<ports>
<port protocol="tcp" portid="80"><state state="open"/><service name="http" product="nginx"/></port>
<port protocol="tcp" portid="443"><state state="open"/><service name="https" product="nginx"/></port>
<port protocol="tcp" portid="22"><state state="filtered"/></port>
</ports>
</host>
<host starttime="1678886411" endtime="1678886420">
<address addr="192.168.1.2" addrtype="ipv4"/>
<hostnames><hostname name="host2.example.com" type="user"/></hostnames>
<ports>
<port protocol="tcp" portid="8080"><state state="open"/><service name="http-proxy"/></port>
</ports>
</host>
</nmaprun>"""
        with open(simulated_output_file, "w") as f:
            f.write(simulated_xml_content)
        self._log(f"Simulated output written to {simulated_output_file}")
        
        # Simulate success
        return subprocess.CompletedProcess(args=command_args, returncode=0, stdout="Simulated stdout", stderr="")

    def run(self):
        self._log(f"Running Nmap for targets: {self.target_scope}")
        
        raw_out_file_name = "nmap_raw.xml"
        raw_out_path_local = self.tool_output_dir / raw_out_file_name
        container_mount_dir = Path("/app/data")
        raw_out_path_container = container_mount_dir / raw_out_file_name

        # Nmap command for service version detection and XML output
        targets_str = " ".join(self.target_scope)
        command_args = ["-sV", "-oX", str(raw_out_path_container), targets_str] # targets_str goes last
        
        try:
            self._run_docker_tool_simulated(
                image_name="kai-nmap",
                command_args=command_args,
                mount_local_dir=raw_out_path_local.parent,
                cap_add=["NET_RAW", "NET_ADMIN"]
            )
            
            # Parse Nmap XML output
            findings = []
            tree = ET.parse(raw_out_path_local)
            root = tree.getroot()

            for host in root.findall('host'):
                ip_addr = host.find('address').get('addr')
                hostnames = [h.get('name') for h in host.findall('hostnames/hostname')]
                
                # Enforce scope on IP and hostnames
                if not self.scope_enforcer(ip_addr) and not any(self.scope_enforcer(h) for h in hostnames):
                    self._log(f"Host {ip_addr} ({hostnames}) is out of scope. Skipping.", level="DEBUG")
                    continue

                for port in host.findall('ports/port'):
                    port_id = port.get('portid')
                    protocol = port.get('protocol')
                    state = port.find('state').get('state')
                    service_element = port.find('service')
                    service_name = service_element.get('name') if service_element is not None else "unknown"
                    product = service_element.get('product') if service_element is not None and 'product' in service_element.attrib else ""

                    # Create a finding for each open/filtered port
                    finding_description = f"Port {port_id}/{protocol} is {state}"
                    if service_name != "unknown":
                        finding_description += f" with service {service_name}"
                    if product:
                        finding_description += f" ({product})"
                    
                    # Store as a normalized finding (simplified for wrapper example)
                    findings.append({
                        "asset": ip_addr, # Simplified for now, should link to Asset ID
                        "type": "Open Port" if state == "open" else "Filtered Port",
                        "severity": "Low" if state == "open" else "Info",
                        "description": finding_description,
                        "tool": "nmap",
                        "details": {"port": port_id, "protocol": protocol, "state": state, "service": service_name, "product": product}
                    })
            
            norm_out_path = self.base_output / "normalized" / f"nmap_findings_{self.run_id}.json"
            with open(norm_out_path, "w") as f:
                json.dump(findings, f, indent=4)
            
            self._log(f"Nmap scan complete. Found {len(findings)} port-related findings. Normalized output to {norm_out_path}")
            return findings

        except subprocess.CalledProcessError as e:
            self._log(f"Nmap Docker execution failed: {e.stderr}", level="ERROR")
            return []
        except ET.ParseError as e:
            self._log(f"Failed to parse Nmap XML output: {e}", level="ERROR")
            return []
        except Exception as e:
            self._log(f"An unexpected error occurred during Nmap run: {e}", level="ERROR")
            return []

# Example of how it would be called from KaiEngine:
# Assuming kai_instance = KaiEngine("example.com") and it provides valid targets and a scope_enforcer.
# nmap_targets = ["192.168.1.1", "host1.example.com"]
# nmap_wrapper = NmapWrapper(
#     run_id=kai_instance.run_id,
#     base_output_dir=kai_instance.base_output,
#     target_scope=nmap_targets,
#     scope_enforcer=kai_instance.enforce_scope
# )
# nmap_findings = nmap_wrapper.run()
