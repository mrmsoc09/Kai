# Kaison K1 Enterprise Platform

## 🚀 Unified Start
We have simplified the startup process into a single CLI tool.

### 1. Start the Platform
To prepare your system and start the platform:
1. Run the bootstrap: `./bootstrap.sh`
2. Run the unified control script: `./k1 start`
This will:
1.  Check for necessary dependencies (Docker, Python).
2.  Launch the **Configuration Wizard** (first run only) to set up:
    *   **AI Keys:** Securely input your OpenAI API Key (required for Kaison Composer).
    *   **Network Privacy:** Configure Whonix Gateway IP/Port for routing tool traffic through Tor.
    *   **Database Credentials:** Auto-generate or set secure passwords.
3.  Boot the entire Docker stack (Frontend, Backend, Database, Redis, Vault, MailHog).

### 2. Configuration Wizard
You can re-run the configuration at any time:
```bash
./k1 setup
```

### 3. Manage the Platform
*   **Stop:** `./k1 stop`
*   **Restart:** `./k1 restart`
*   **View Logs:** `./k1 logs`

---

## 🔑 Key Management (Bulk Import)
Kaison K1 now supports automated bulk import for your 75+ external API keys (Shodan, ZoomEye, etc.).

1.  Start the platform (`./k1 start`).
2.  Log in to the **Frontend Dashboard** (http://localhost:8081).
3.  Navigate to **Settings -> Key Management**.
4.  **Upload** your CSV or PDF file containing the keys.
    *   **CSV Format:** `Service, Key`
    *   **PDF:** The system will auto-parse "Service: Key" lines.
5.  Keys are securely encrypted and stored in **HashiCorp Vault**.

---

## 🤖 Kaison Composer
Access the advanced AI engine via the sidebar **"Kaison Composer"**.
*   **Model:** Enforced to use `gpt-4.1` for optimal reasoning and rate limits.
*   **UI:** Fully rebranded with an Enterprise Dark Mode theme.

---

## 🛡️ Security & Privacy
*   **Whonix Integration:** If configured, all outgoing tool traffic from the worker container is routed through your local Whonix Gateway.
*   **Zero-Trust:** Tools run in isolated Docker containers.
*   **Audit Logs:** All actions are cryptographically signed and logged.

---

## 📦 Software Bill of Materials (SBOM)
Kaison K1 leverages elite open-source security tools. All tools are automatically managed within the worker container.

| Tool | Source Repository | Function |
| :--- | :--- | :--- |
| **Nuclei** | [projectdiscovery/nuclei](https://github.com/projectdiscovery/nuclei) | Template-based vulnerability scanning |
| **TruffleHog** | [trufflesecurity/trufflehog](https://github.com/trufflesecurity/trufflehog) | Secret and credential auditing |
| **Subfinder** | [projectdiscovery/subfinder](https://github.com/projectdiscovery/subfinder) | Passive subdomain discovery |
| **Naabu** | [projectdiscovery/naabu](https://github.com/projectdiscovery/naabu) | High-speed port scanning |
| **Httpx** | [projectdiscovery/httpx](https://github.com/projectdiscovery/httpx) | HTTP toolkit for tech fingerprinting |
| **Amass** | [owasp-amass/amass](https://github.com/owasp-amass/amass) | In-depth attack surface mapping |
| **FFUF** | [ffuf/ffuf](https://github.com/ffuf/ffuf) | Fast web fuzzing and discovery |
| **Katana** | [projectdiscovery/katana](https://github.com/projectdiscovery/katana) | Headless web crawling |
| **Dnsx** | [projectdiscovery/dnsx](https://github.com/projectdiscovery/dnsx) | Multipurpose DNS toolkit |
| **theHarvester** | [laramies/theHarvester](https://github.com/laramies/theHarvester) | OSINT for emails, names, and subdomains |

---

## 📂 Legacy Documentation
Old documentation files have been moved to `docs/archive/` to reduce clutter.
