"""
Reproducible payload and script generator.
Converts exploitation findings into standalone curl commands, Python scripts, and exploit code.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import json
import base64
import html

logger = logging.getLogger(__name__)


class ScriptType(str, Enum):
    """Type of reproduction script."""

    CURL = "curl"
    PYTHON_REQUESTS = "python_requests"
    PYTHON_EXPLOIT = "python_exploit"
    BASH = "bash"


@dataclass
class ReproductionScript:
    """Reproducible exploitation script."""

    task_id: str
    script_type: ScriptType
    content: str
    language: str
    filename: str
    description: str
    prerequisites: list[str] = None
    expected_output: str = ""

    def __post_init__(self):
        if self.prerequisites is None:
            self.prerequisites = []

    def to_file_content(self) -> str:
        """Get content ready to write to file."""
        if self.script_type == ScriptType.CURL:
            return self.content

        if self.script_type in (
            ScriptType.PYTHON_REQUESTS,
            ScriptType.PYTHON_EXPLOIT,
        ):
            header = "#!/usr/bin/env python3\n"
            header += f"# Generated reproduction script for {self.task_id}\n"
            header += f"# {self.description}\n\n"
            return header + self.content

        if self.script_type == ScriptType.BASH:
            header = "#!/bin/bash\n"
            header += f"# Generated reproduction script for {self.task_id}\n"
            header += f"# {self.description}\n\n"
            return header + self.content

        return self.content


class ReproScriptGenerator:
    """
    Generates reproducible exploitation scripts from tool outputs.
    Creates curl commands, Python requests, and standalone exploits.
    """

    def __init__(self):
        """Initialize repro script generator."""
        self.generated_scripts: Dict[str, list[ReproductionScript]] = {}

    async def generate_curl_command(
        self,
        task_id: str,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[str] = None,
        description: str = "",
    ) -> ReproductionScript:
        """
        Generate curl command from HTTP request.

        Args:
            task_id: Task identifier
            method: HTTP method
            url: Request URL
            headers: HTTP headers dict
            body: Request body (optional)
            description: What the curl command does

        Returns:
            ReproductionScript with curl command
        """
        # Build curl command
        curl_parts = [f"curl -X {method}"]

        # Add headers
        for header_name, header_value in headers.items():
            # Skip sensitive headers
            if header_name.lower() in ("authorization", "x-api-key", "cookie"):
                curl_parts.append(f'  -H "{header_name}: <REDACTED>"')
            else:
                # Escape quotes in header values
                escaped_value = header_value.replace('"', '\\"')
                curl_parts.append(f'  -H "{header_name}: {escaped_value}"')

        # Add body
        if body:
            # Escape special characters
            escaped_body = body.replace('"', '\\"').replace("\n", "\\n")
            curl_parts.append(f'  -d "{escaped_body}"')

        # Add URL
        curl_parts.append(f'  "{url}"')

        curl_command = "\\\n".join(curl_parts)

        script = ReproductionScript(
            task_id=task_id,
            script_type=ScriptType.CURL,
            content=curl_command,
            language="bash",
            filename=f"{task_id}_repro.sh",
            description=description,
            prerequisites=["curl"],
            expected_output="Server response showing successful exploitation",
        )

        if task_id not in self.generated_scripts:
            self.generated_scripts[task_id] = []
        self.generated_scripts[task_id].append(script)

        logger.info(
            f"Generated curl command for {task_id}"
        )

        return script

    async def generate_python_requests(
        self,
        task_id: str,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None,
        description: str = "",
    ) -> ReproductionScript:
        """
        Generate Python requests script.

        Args:
            task_id: Task identifier
            method: HTTP method
            url: Request URL
            headers: HTTP headers dict
            body: Request body (optional)
            cookies: Cookies dict (optional)
            description: What the script does

        Returns:
            ReproductionScript with Python code
        """
        python_code = """import requests
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
URL = {url}
METHOD = "{method}"
HEADERS = {headers}
COOKIES = {cookies}
BODY = {body}

# Setup session with retry logic
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Make request
try:
    response = session.request(
        method=METHOD,
        url=URL,
        headers=HEADERS,
        cookies=COOKIES,
        data=BODY,
        timeout=30,
        verify=False,  # WARNING: Disables SSL verification
    )

    print(f"Status Code: {{response.status_code}}")
    print(f"Response Headers: {{dict(response.headers)}}")
    print(f"Response Body: {{response.text[:500]}}")

    # Check for successful exploitation
    if response.status_code in (200, 201, 204):
        print("[+] Exploitation successful!")
    else:
        print("[-] Exploitation may have failed")

except Exception as e:
    print(f"[-] Error: {{str(e)}}")
""".format(
            url=json.dumps(url),
            method=method,
            headers=json.dumps(
                {
                    k: (
                        "<REDACTED>"
                        if k.lower()
                        in (
                            "authorization",
                            "x-api-key",
                            "cookie",
                        )
                        else v
                    )
                    for k, v in headers.items()
                },
                indent=2,
            ),
            cookies=json.dumps(cookies or {}, indent=2),
            body=json.dumps(body, indent=2) if body else "None",
        )

        script = ReproductionScript(
            task_id=task_id,
            script_type=ScriptType.PYTHON_REQUESTS,
            content=python_code,
            language="python",
            filename=f"{task_id}_repro.py",
            description=description,
            prerequisites=["requests"],
            expected_output="Server response with status code 200/201",
        )

        if task_id not in self.generated_scripts:
            self.generated_scripts[task_id] = []
        self.generated_scripts[task_id].append(script)

        logger.info(f"Generated Python requests script for {task_id}")

        return script

    async def generate_exploit_script(
        self,
        task_id: str,
        vulnerability_type: str,
        target_url: str,
        exploitation_steps: list[str],
        payload: str,
        description: str = "",
    ) -> ReproductionScript:
        """
        Generate standalone exploit script for complex chains.

        Args:
            task_id: Task identifier
            vulnerability_type: Type of vulnerability (RCE, SSRF, etc.)
            target_url: Target URL
            exploitation_steps: List of step descriptions
            payload: The actual payload or exploitation code
            description: Overall description

        Returns:
            ReproductionScript with exploit code
        """
        exploit_code = f"""#!/usr/bin/env python3
\"\"\"
Standalone exploit for {vulnerability_type} vulnerability.
Task: {task_id}
Description: {description}

Exploitation Steps:
{chr(10).join(f'  {i+1}. {{step}}' for i, step in enumerate(exploitation_steps))}
\"\"\"

import requests
import argparse
import sys
import time

class {{}}Exploit:
    def __init__(self, target_url, timeout=30):
        self.target_url = target_url
        self.timeout = timeout
        self.session = requests.Session()

    def exploit(self):
        \"\"\"Execute the exploitation chain.\"\"\"
        try:
            print(f"[*] Targeting: {{self.target_url}}")

            # Execute exploitation steps
            {self._indent_code(payload, 12)}

            print("[+] Exploitation successful!")
            return True

        except Exception as e:
            print(f"[-] Exploitation failed: {{str(e)}}")
            return False

    def verify(self):
        \"\"\"Verify successful exploitation.\"\"\"
        print("[*] Verifying exploitation...")
        # Add verification logic here

def main():
    parser = argparse.ArgumentParser(
        description="Exploit for {vulnerability_type}"
    )
    parser.add_argument(
        "target_url",
        help="Target URL (e.g., http://example.com)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds"
    )

    args = parser.parse_args()

    exploit = {{}}Exploit(args.target_url, args.timeout)
    success = exploit.exploit()

    if success:
        exploit.verify()
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
""".replace(
            "{{}}",
            vulnerability_type.replace(" ", ""),
        )

        script = ReproductionScript(
            task_id=task_id,
            script_type=ScriptType.PYTHON_EXPLOIT,
            content=exploit_code,
            language="python",
            filename=f"{task_id}_exploit.py",
            description=f"Standalone exploit for {vulnerability_type}",
            prerequisites=["requests", "python3"],
            expected_output="[+] Exploitation successful!",
        )

        if task_id not in self.generated_scripts:
            self.generated_scripts[task_id] = []
        self.generated_scripts[task_id].append(script)

        logger.info(f"Generated exploit script for {task_id}")

        return script

    @staticmethod
    def _indent_code(code: str, spaces: int) -> str:
        """Indent code block."""
        indent = " " * spaces
        return "\n".join(
            f"{indent}{line}" if line.strip() else line
            for line in code.split("\n")
        )

    async def get_scripts_for_task(
        self, task_id: str
    ) -> list[ReproductionScript]:
        """Get all generated scripts for a task."""
        return self.generated_scripts.get(task_id, [])

    def get_script_stats(self) -> Dict[str, Any]:
        """Get statistics about generated scripts."""
        total_scripts = sum(
            len(scripts)
            for scripts in self.generated_scripts.values()
        )
        by_type = {}

        for scripts in self.generated_scripts.values():
            for script in scripts:
                script_type = script.script_type.value
                by_type[script_type] = by_type.get(script_type, 0) + 1

        return {
            "total_scripts": total_scripts,
            "by_type": by_type,
            "tasks_with_scripts": len(self.generated_scripts),
        }


# Global repro generator instance
_repro_generator: Optional[ReproScriptGenerator] = None


async def get_repro_generator() -> ReproScriptGenerator:
    """Get or create global repro script generator."""
    global _repro_generator

    if _repro_generator is None:
        _repro_generator = ReproScriptGenerator()

    return _repro_generator
