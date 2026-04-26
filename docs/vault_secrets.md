# Vault Secrets Management

KAISON AI uses HashiCorp Vault for encrypted secret storage. All credentials are stored in Vault and never appear in plaintext in configuration files or logs.

## Docker Registry Credentials

**Path**: `secret/data/kaison/docker`

**Fields**:
- `username` — Docker Hub username or registry username
- `password` — Docker Hub access token or registry password

KAISON AI checks this path automatically on every `./k1 start` and `./bootstrap.sh` run.

### Automatic Flow

1. **Check Local Auth**: If Docker is already authenticated locally (via ~/.docker/config.json), skip Vault check
2. **Check Vault**: If not authenticated locally, fetch credentials from Vault
3. **Attempt Login**: Login with Vault credentials if found
4. **Prompt User**: If Vault credentials fail or Vault is unavailable, prompt user interactively
5. **Store in Vault**: After successful authentication, store credentials in Vault (if VAULT_TOKEN is set)

### Manual Storage

Pre-store Docker credentials in Vault before startup:

```bash
# Ensure Vault is running and VAULT_TOKEN is set
vault kv put secret/kaison/docker \
  username=your_docker_username \
  password=your_docker_access_token
```

### Security Notes

- Credentials are **encrypted at rest** in Vault using the transit engine
- Credentials are **never logged** in K1 output
- Credentials are **never stored in plaintext** locally
- `.docker/config.json` is managed by Docker (uses credential helpers if configured)
- K1 respects Docker's native credential helpers (credsStore)

### Troubleshooting

**Docker daemon not running**
```bash
sudo systemctl start docker
./k1 start
```

**Invalid credentials in Vault**
```bash
# Delete old credentials and re-run bootstrap
vault kv delete secret/kaison/docker
./bootstrap.sh
# Provide new credentials when prompted
```

**Can't reach Vault**
```bash
# If VAULT_TOKEN is not set, K1 will prompt for credentials
# and attempt to store them (if Vault becomes available later)
VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=your_token ./k1 start
```

---

## Other Secrets (Future)

Additional secret paths can be stored at:
- `secret/data/kaison/api-keys` — External API credentials
- `secret/data/kaison/database` — Database credentials
- `secret/data/kaison/ssh-keys` — SSH keys for infrastructure
- `secret/data/kaison/network/<provider_id>` — VPN/proxy credentials for egress automation

### Network Credential GUI Workflow

The **Vault Keys** frontend page supports direct storage of structured network credentials.

- Endpoint: `POST /vault/network/providers/{provider_id}/credentials`
- Status: `GET /vault/network/providers/status`
- Supported fields:
  - `username`
  - `password`
  - `pat`
  - `api_key`
  - `endpoint`
  - `proxy_url`
  - `notes`

Use provider ids such as:

- `protonvpn`
- `mullvadvpn`
- `decodo_residential`
- `decodo_mobile`

To render these into a local env file for rotation automation:

```bash
./scripts/build_network_egress_env.py --output runtime/network/egress.env
```

All follow the same automated check → Vault → prompt → store pattern as Docker credentials.
