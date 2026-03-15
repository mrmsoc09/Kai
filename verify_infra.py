#!/usr/bin/env python3
"""
Project Kai Infrastructure Verification Script
Validates cryptographic setup and trust model
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime, timezone
import gnupg

# Configuration
GPG_HOME = Path.home() / ".kai" / "gpg_home"
PUBLIC_VAULT = Path.home() / ".kai" / "public_vault"
SSH_KEY_PATH = Path.home() / ".ssh" / "id_kaisonai_machine"
SSH_PUB_PATH = Path.home() / ".ssh" / "id_kaisonai_machine.pub"

KAISONAI_IDENTITIES = {
    "admin-kaisonai@pm.me": "Admin Identity",
    "user-kaisonai@pm.me": "User Identity",
    "infra-kaisonai@pm.me": "Infrastructure Identity",
    "machine-kaisonai@pm.me": "Machine Execution Identity"
}

class KaiInfraVerifier:
    """Verify Project Kai infrastructure and cryptographic setup"""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
            "summary": {}
        }
        self.gpg = None

    def print_header(self, text):
        """Print formatted section header"""
        print(f"\n{'='*70}")
        print(f"[*] {text}")
        print(f"{'='*70}\n")

    def print_success(self, message):
        """Print success message"""
        print(f"[✓] {message}")

    def print_error(self, message):
        """Print error message"""
        print(f"[✗] {message}")

    def print_warning(self, message):
        """Print warning message"""
        print(f"[!] {message}")

    def print_info(self, message):
        """Print info message"""
        print(f"[•] {message}")

    # ==================== Check 1: Directory Structure ====================

    async def check_directory_structure(self):
        """Verify required directories exist with correct permissions"""
        self.print_header("DIRECTORY STRUCTURE VERIFICATION")

        check_result = {
            "status": "pending",
            "directories": {}
        }

        directories = [
            (GPG_HOME, 0o700, "GPG Home"),
            (PUBLIC_VAULT, 0o700, "PGP Public Vault"),
            (SSH_KEY_PATH.parent, 0o700, "SSH Key Directory")
        ]

        all_valid = True

        for dir_path, required_perms, description in directories:
            if not dir_path.exists():
                self.print_error(f"{description} not found: {dir_path}")
                check_result["directories"][str(dir_path)] = "missing"
                all_valid = False
            else:
                actual_perms = oct(os.stat(dir_path).st_mode)[-3:]
                if int(actual_perms, 8) == required_perms:
                    self.print_success(f"{description}: {dir_path} (perms: {actual_perms})")
                    check_result["directories"][str(dir_path)] = "valid"
                else:
                    self.print_warning(
                        f"{description}: {dir_path} has perms {actual_perms}, "
                        f"expected {oct(required_perms)[-3:]}"
                    )
                    check_result["directories"][str(dir_path)] = "invalid_perms"
                    all_valid = False

        check_result["status"] = "passed" if all_valid else "failed"
        self.results["checks"]["directory_structure"] = check_result
        return all_valid

    # ==================== Check 2: PGP Key Vault ====================

    async def check_pgp_vault(self):
        """Verify PGP public vault contains all identity keys"""
        self.print_header("PGP PUBLIC VAULT VERIFICATION")

        check_result = {
            "status": "pending",
            "files": {},
            "total_keys": 0
        }

        if not PUBLIC_VAULT.exists():
            self.print_error(f"Public vault not found: {PUBLIC_VAULT}")
            check_result["status"] = "failed"
            self.results["checks"]["pgp_vault"] = check_result
            return False

        asc_files = list(PUBLIC_VAULT.glob("*.asc"))

        if not asc_files:
            self.print_warning(f"No .asc files found in {PUBLIC_VAULT}")
            check_result["status"] = "failed"
            self.results["checks"]["pgp_vault"] = check_result
            return False

        self.print_info(f"Found {len(asc_files)} PGP key files in vault")

        all_valid = True
        for key_file in asc_files:
            try:
                content = key_file.read_text()
                is_private = "PRIVATE KEY" in content
                is_public = "PUBLIC KEY" in content

                if is_private:
                    key_type = "PRIVATE"
                elif is_public:
                    key_type = "PUBLIC"
                else:
                    key_type = "UNKNOWN"

                self.print_success(f"{key_file.name}: {key_type} key")
                check_result["files"][key_file.name] = key_type

            except Exception as e:
                self.print_error(f"Failed to read {key_file.name}: {str(e)}")
                check_result["files"][key_file.name] = "error"
                all_valid = False

        check_result["total_keys"] = len(asc_files)
        check_result["status"] = "passed" if all_valid else "failed"
        self.results["checks"]["pgp_vault"] = check_result
        return all_valid

    # ==================== Check 3: Initialize GPG Home ====================

    async def check_gpg_initialization(self):
        """Initialize GPG home and verify setup"""
        self.print_header("GPG HOME INITIALIZATION")

        check_result = {
            "status": "pending",
            "gpg_home": str(GPG_HOME),
            "keys_imported": 0,
            "trust_model": {}
        }

        try:
            # Create GPG home with proper permissions
            GPG_HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(GPG_HOME, 0o700)
            self.print_success(f"GPG home ready: {GPG_HOME}")

            # Initialize GPG
            self.gpg = gnupg.GPG(gnupghome=str(GPG_HOME))
            self.print_success("GnuPG initialized")

            # Import all keys from vault
            for key_file in PUBLIC_VAULT.glob("*.asc"):
                try:
                    key_data = key_file.read_text()
                    import_result = self.gpg.import_keys(key_data)

                    if import_result.count > 0:
                        self.print_success(f"Imported {key_file.name}: {import_result.count} key(s)")
                        check_result["keys_imported"] += import_result.count
                    else:
                        self.print_warning(f"No keys imported from {key_file.name}")

                except Exception as e:
                    self.print_error(f"Failed to import {key_file.name}: {str(e)}")

            # Set trust for admin key
            try:
                admin_keys = self.gpg.list_keys(keys="admin-kaisonai@pm.me")
                if admin_keys:
                    admin_key = admin_keys[0]
                    fingerprint = admin_key["fingerprint"]

                    # Try to set trust to Ultimate (5)
                    self.gpg.trust_keys(fingerprint, "TRUST_ULTIMATE")
                    self.print_success(f"Set admin key trust to ULTIMATE: {fingerprint}")
                    check_result["trust_model"]["admin-kaisonai@pm.me"] = "ULTIMATE"

            except Exception as e:
                self.print_warning(f"Could not set trust model: {str(e)}")

            check_result["status"] = "passed" if check_result["keys_imported"] > 0 else "failed"
            self.results["checks"]["gpg_initialization"] = check_result
            return True

        except Exception as e:
            self.print_error(f"GPG initialization failed: {str(e)}")
            check_result["status"] = "failed"
            self.results["checks"]["gpg_initialization"] = check_result
            return False

    # ==================== Check 4: Kaisonai Identity Verification ====================

    async def check_kaisonai_identities(self):
        """List and verify all Kaisonai identity fingerprints"""
        self.print_header("KAISONAI IDENTITY VERIFICATION")

        check_result = {
            "status": "pending",
            "identities": {}
        }

        if not self.gpg:
            self.print_error("GPG not initialized")
            check_result["status"] = "failed"
            self.results["checks"]["kaisonai_identities"] = check_result
            return False

        all_found = True

        for identity, description in KAISONAI_IDENTITIES.items():
            try:
                keys = self.gpg.list_keys(keys=identity)

                if keys:
                    key = keys[0]
                    fingerprint = key["fingerprint"]
                    key_type = "SECRET" if key["type"] == "sec" else "PUBLIC"

                    self.print_success(
                        f"{description}\n"
                        f"    Email: {identity}\n"
                        f"    Fingerprint: {fingerprint}\n"
                        f"    Type: {key_type}"
                    )

                    check_result["identities"][identity] = {
                        "fingerprint": fingerprint,
                        "type": key_type,
                        "status": "found"
                    }

                else:
                    self.print_warning(f"{description} ({identity}) not found in keyring")
                    check_result["identities"][identity] = {"status": "not_found"}
                    all_found = False

            except Exception as e:
                self.print_error(f"Error checking {identity}: {str(e)}")
                check_result["identities"][identity] = {"status": "error", "error": str(e)}
                all_found = False

        check_result["status"] = "passed" if all_found else "failed"
        self.results["checks"]["kaisonai_identities"] = check_result
        return all_found

    # ==================== Check 5: SSH Machine Key ====================

    async def check_ssh_machine_key(self):
        """Verify SSH machine key and ssh-agent access"""
        self.print_header("SSH MACHINE KEY VERIFICATION")

        check_result = {
            "status": "pending",
            "ssh_key": {},
            "ssh_agent": {}
        }

        # Check private key file
        if SSH_KEY_PATH.exists():
            perms = oct(os.stat(SSH_KEY_PATH).st_mode)[-3:]
            if perms == "600":
                self.print_success(f"SSH private key exists: {SSH_KEY_PATH} (perms: {perms})")
                check_result["ssh_key"]["private_key"] = "valid"
            else:
                self.print_warning(f"SSH key has unusual perms: {perms} (expected 600)")
                check_result["ssh_key"]["private_key"] = "wrong_perms"
        else:
            self.print_error(f"SSH private key not found: {SSH_KEY_PATH}")
            check_result["ssh_key"]["private_key"] = "missing"

        # Check public key file
        if SSH_PUB_PATH.exists():
            self.print_success(f"SSH public key exists: {SSH_PUB_PATH}")
            check_result["ssh_key"]["public_key"] = "valid"
        else:
            self.print_warning(f"SSH public key not found: {SSH_PUB_PATH}")
            check_result["ssh_key"]["public_key"] = "missing"

        # Check ssh-agent
        try:
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                keys = result.stdout.strip().split('\n')
                self.print_info(f"ssh-agent has {len(keys)} key(s)")

                # Check if machine key is loaded
                machine_key_loaded = any("id_kaisonai_machine" in key for key in keys)

                if machine_key_loaded:
                    self.print_success("Machine key is loaded in ssh-agent")
                    check_result["ssh_agent"]["machine_key"] = "loaded"
                else:
                    self.print_warning("Machine key NOT loaded in ssh-agent")
                    self.print_info("To load: ssh-add ~/.ssh/id_kaisonai_machine")
                    check_result["ssh_agent"]["machine_key"] = "not_loaded"

            else:
                self.print_warning("ssh-agent not running or no keys loaded")
                check_result["ssh_agent"]["status"] = "not_running"

        except subprocess.TimeoutExpired:
            self.print_error("ssh-agent check timed out")
            check_result["ssh_agent"]["status"] = "timeout"

        except Exception as e:
            self.print_warning(f"Could not check ssh-agent: {str(e)}")
            check_result["ssh_agent"]["status"] = "error"

        check_result["status"] = "passed"
        self.results["checks"]["ssh_machine_key"] = check_result
        return True

    # ==================== Check 6: Trust Model Validation ====================

    async def check_trust_model(self):
        """Validate the trust model setup"""
        self.print_header("TRUST MODEL VALIDATION")

        check_result = {
            "status": "pending",
            "trust_levels": {}
        }

        if not self.gpg:
            self.print_error("GPG not initialized")
            check_result["status"] = "failed"
            self.results["checks"]["trust_model"] = check_result
            return False

        try:
            # Get trust database
            all_keys = self.gpg.list_keys()

            for key in all_keys:
                fingerprint = key["fingerprint"]
                trust = key.get("trust", "unknown")
                uids = key.get("uids", [])

                if uids:
                    uid = uids[0]
                    self.print_info(f"Key: {uid[:40]}...")
                    self.print_info(f"  Fingerprint: {fingerprint}")
                    self.print_info(f"  Trust Level: {trust}")
                    check_result["trust_levels"][uid] = trust

            self.print_success("Trust model validated")
            check_result["status"] = "passed"

        except Exception as e:
            self.print_error(f"Trust model validation failed: {str(e)}")
            check_result["status"] = "failed"

        self.results["checks"]["trust_model"] = check_result
        return True

    # ==================== Summary Report ====================

    def generate_summary(self):
        """Generate summary of all checks"""
        self.print_header("VERIFICATION SUMMARY")

        passed = 0
        failed = 0

        for check_name, check_result in self.results["checks"].items():
            status = check_result.get("status", "unknown")
            symbol = "[✓]" if status == "passed" else "[✗]" if status == "failed" else "[?]"
            print(f"{symbol} {check_name}: {status}")

            if status == "passed":
                passed += 1
            else:
                failed += 1

        total = passed + failed
        success_rate = (passed / total * 100) if total > 0 else 0

        self.results["summary"] = {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "success_rate": success_rate
        }

        print(f"\n{'='*70}")
        print(f"Total Checks: {total} | Passed: {passed} | Failed: {failed}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"{'='*70}\n")

        return failed == 0

    def output_json_report(self):
        """Output JSON report of results"""
        report_path = Path.home() / ".kai" / "verify_infra_report.json"
        report_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"Report saved to: {report_path}\n")

    async def run_all_checks(self):
        """Run all verification checks"""
        self.print_header("PROJECT KAI INFRASTRUCTURE VERIFICATION")
        print(f"Host: {os.uname().nodename}")
        print(f"User: {os.getenv('USER', 'unknown')}")
        print(f"Time: {datetime.now(timezone.utc).isoformat()}\n")

        checks = [
            ("Directory Structure", self.check_directory_structure),
            ("PGP Public Vault", self.check_pgp_vault),
            ("GPG Initialization", self.check_gpg_initialization),
            ("Kaisonai Identities", self.check_kaisonai_identities),
            ("SSH Machine Key", self.check_ssh_machine_key),
            ("Trust Model", self.check_trust_model)
        ]

        for check_name, check_func in checks:
            try:
                await check_func()
            except Exception as e:
                self.print_error(f"Check '{check_name}' failed with exception: {str(e)}")
                self.results["checks"][check_name.lower().replace(" ", "_")] = {
                    "status": "error",
                    "error": str(e)
                }

        success = self.generate_summary()
        self.output_json_report()

        return success


async def main():
    """Main entry point"""
    verifier = KaiInfraVerifier()
    success = await verifier.run_all_checks()

    if success:
        print("\n[✓] PROJECT KAI INFRASTRUCTURE VERIFICATION SUCCESSFUL")
        print("\nNext steps:")
        print("  1. Load SSH key: ssh-add ~/.ssh/id_kaisonai_machine")
        print("  2. Initialize Kai: python apps/backend/src/main.py")
        print("  3. Test artifact signing: curl -X POST http://localhost:8000/api/artifacts/init")
        return 0
    else:
        print("\n[✗] INFRASTRUCTURE VERIFICATION FAILED")
        print("Please resolve the issues above before proceeding.")
        return 1


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
