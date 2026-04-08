#!/usr/bin/env python3
import os
import json
import getpass
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- Configuration ---
VAULT_DIR = Path(".k1")
VAULT_FILE = VAULT_DIR / "vault.enc"

def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

def bootstrap_k1():
    print("--- K1 SOVEREIGN BOOTSTRAPPER (STAGE 22) ---")
    VAULT_DIR.mkdir(exist_ok=True)
    
    passphrase = getpass.getpass("Enter MASTER PASSPHRASE to lock your Sovereign Vault: ")
    confirm = getpass.getpass("Confirm MASTER PASSPHRASE: ")
    
    if passphrase != confirm:
        print("Error: Passphrases do not match.")
        return

    creds = {
        "cloud": {},
        "vpn": {},
        "proxies": []
    }

    # 1. Cloud API Keys
    print("\n[CLOUD INFRASTRUCTURE]")
    creds["cloud"]["aws"] = {
        "key": input("AWS Access Key: "),
        "secret": getpass.getpass("AWS Secret Key: ")
    }
    creds["cloud"]["gcp"] = {
        "project_id": input("GCP Project ID: "),
        "service_account_json": input("GCP Service Account JSON (Path or Paste): ")
    }
    creds["cloud"]["oracle"] = {
        "user_ocid": input("Oracle User OCID: "),
        "tenancy_ocid": input("Oracle Tenancy OCID: "),
        "fingerprint": input("Oracle API Fingerprint: "),
        "key_content": getpass.getpass("Oracle Private Key Content: ")
    }
    creds["cloud"]["digitalocean"] = {
        "token": getpass.getpass("DigitalOcean API Token: ")
    }

    # 2. VPN Options
    print("\n[VPN CONFIGURATION]")
    creds["vpn"]["mullvad_id"] = getpass.getpass("Mullvad Account ID: ")
    creds["vpn"]["proton"] = {
        "user": input("ProtonVPN Username: "),
        "pass": getpass.getpass("ProtonVPN Password: ")
    }

    # 3. Residential Proxies
    print("\n[RESIDENTIAL PROXIES]")
    proxy_url = input("Residential Proxy URL (e.g. socks5://user:pass@host:port): ")
    if proxy_url:
        creds["proxies"].append(proxy_url)

    # 4. Encryption & Persistence
    salt = os.urandom(16)
    key = derive_key(passphrase, salt)
    f = Fernet(key)
    
    encrypted_data = f.encrypt(json.dumps(creds).encode())
    
    with open(VAULT_FILE, "wb") as out:
        out.write(salt + encrypted_data)
    
    print(f"\nSUCCESS: Sovereign Vault created at {VAULT_FILE}")
    print("Whonix dependencies have been decoupled. K1 is now Cloud-Agnostic.")

if __name__ == "__main__":
    try:
        bootstrap_k1()
    except KeyboardInterrupt:
        print("\nBootstrap aborted.")
