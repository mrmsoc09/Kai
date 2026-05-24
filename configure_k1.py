#!/usr/bin/env python3
import os
import sys
import getpass
import secrets
import string

def generate_secret(length=32):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(length))

def prompt_user(question, default=None, is_secret=False):
    prompt_text = f"{question} "
    if default:
        masked = default[:6] + "…" if (is_secret and len(default) > 6) else default
        prompt_text += f"[{masked}]: "
    else:
        prompt_text += ": "

    if is_secret:
        value = getpass.getpass(prompt_text)
    else:
        value = input(prompt_text)

    if not value and default:
        return default
    return value.strip()

def prompt_choice(question, choices, default=None):
    """Present a numbered menu and return the chosen value."""
    print(f"\n{question}")
    for i, (label, val) in enumerate(choices, 1):
        marker = " (default)" if val == default else ""
        print(f"  {i}) {label}{marker}")
    while True:
        raw = input(f"Select [1-{len(choices)}]: ").strip()
        if not raw and default:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1][1]
        print(f"  Please enter a number between 1 and {len(choices)}.")

def main():
    print("\n" + "="*60)
    print("   KAISON K1 PLATFORM CONFIGURATION WIZARD")
    print("="*60 + "\n")

    env_path = ".env"
    existing_config = {}

    if os.path.exists(env_path):
        print(f"Found existing configuration at {env_path}. Values will be updated.")
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    existing_config[k] = v

    # ── 1. AI / LLM Configuration ──────────────────────────────────────────
    print("\n--- AI / LLM Provider Configuration ---")
    print("Enter API keys for the providers you want to use.")
    print("Press Enter to keep an existing key or skip an unused provider.\n")

    openai_key = prompt_user(
        "OpenAI API Key (gpt-4.1, gpt-4o, …)",
        default=existing_config.get("OPENAI_API_KEY"),
        is_secret=True,
    )

    anthropic_key = prompt_user(
        "Anthropic API Key (claude-opus-4, claude-sonnet-4, …)",
        default=existing_config.get("ANTHROPIC_API_KEY"),
        is_secret=True,
    )

    gemini_key = prompt_user(
        "Google Gemini API Key (gemini-2.0-flash, gemini-1.5-pro, …)",
        default=existing_config.get("GEMINI_API_KEY"),
        is_secret=True,
    )

    openrouter_key = prompt_user(
        "OpenRouter API Key (multi-model gateway)",
        default=existing_config.get("OPENROUTER_API_KEY"),
        is_secret=True,
    )

    # Build list of configured providers so user can pick primary
    configured = []
    if openai_key and not openai_key.startswith("replace"):
        configured.append(("OpenAI", "openai"))
    if anthropic_key and not anthropic_key.startswith("replace"):
        configured.append(("Anthropic", "anthropic"))
    if gemini_key and not gemini_key.startswith("replace"):
        configured.append(("Google Gemini", "gemini"))
    if openrouter_key and not openrouter_key.startswith("replace"):
        configured.append(("OpenRouter", "openrouter"))

    existing_primary = existing_config.get("K1_PRIMARY_LLM_PROVIDER", "openai")

    if len(configured) > 1:
        primary_provider = prompt_choice(
            "Which provider should be the PRIMARY (used by default)?",
            configured,
            default=existing_primary,
        )
    elif len(configured) == 1:
        primary_provider = configured[0][1]
        print(f"\nPrimary provider set to: {configured[0][0]}")
    else:
        primary_provider = "openai"
        print("\nNo API keys entered — defaulting primary provider to 'openai'.")

    # Fallback list: all configured providers except primary
    fallback_providers = ",".join(v for _, v in configured if v != primary_provider)

    # Primary model per provider
    primary_model_map = {
        "openai": "gpt-4.1",
        "anthropic": "claude-opus-4-7-20251101",
        "gemini": "gemini-2.0-flash",
        "openrouter": "openrouter/auto",
    }
    primary_model = primary_model_map.get(primary_provider, "gpt-4.1")

    # ── 2. Network / Privacy ───────────────────────────────────────────────
    print("\n--- Network & Privacy ---")
    use_whonix = prompt_user(
        "Route tool traffic through a local Whonix/Tor Gateway?",
        default=existing_config.get("K1_USE_TOR", "no"),
    ).lower()

    http_proxy = ""
    https_proxy = ""

    if use_whonix in ['y', 'yes', 'true', '1']:
        gateway_ip = prompt_user("Gateway IP", default="127.0.0.1")
        gateway_port = prompt_user("Gateway Port", default="9050")
        proxy_url = f"http://{gateway_ip}:{gateway_port}"
        print(f"Configuring proxy to: {proxy_url}")
        http_proxy = proxy_url
        https_proxy = proxy_url
    else:
        print("Using direct connection (No Tor/Whonix).")

    # ── 3. Secrets ─────────────────────────────────────────────────────────
    print("\n--- Generating Secure Tokens ---")
    jwt_secret = existing_config.get("JWT_SECRET_KEY") or generate_secret(64)
    postgres_password = existing_config.get("POSTGRES_PASSWORD") or generate_secret(32)

    # ── 4. Write .env ──────────────────────────────────────────────────────
    print(f"\nWriting configuration to {env_path}...")

    env_content = f"""# Kaison K1 Environment Configuration
# Generated by ./k1 setup

# ── AI / LLM Providers ───────────────────────────────────────────────────
# Primary provider used by the platform (openai | anthropic | gemini | openrouter)
K1_PRIMARY_LLM_PROVIDER={primary_provider}
K1_PRIMARY_LLM_MODEL={primary_model}
K1_FALLBACK_LLM_PROVIDERS={fallback_providers}

# OpenAI
OPENAI_API_KEY={openai_key or ""}

# Anthropic
ANTHROPIC_API_KEY={anthropic_key or ""}

# Google Gemini
GEMINI_API_KEY={gemini_key or ""}

# OpenRouter  (set OPENROUTER_BASE_URL if using a custom endpoint)
OPENROUTER_API_KEY={openrouter_key or ""}
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Legacy alias kept for backward compatibility
LLM_PROVIDER={primary_provider}
K1_PATCH_LLM_MODEL={primary_model}

# ── Infrastructure ────────────────────────────────────────────────────────
POSTGRES_USER=k1
POSTGRES_PASSWORD={postgres_password}
POSTGRES_DB=k1
# asyncpg driver required by SQLAlchemy async engine
DATABASE_URL=postgresql+asyncpg://k1:{postgres_password}@postgres:5432/k1
# Redis password must match the requirepass value in docker-compose.dev.yml
REDIS_URL=redis://:K1_SecR3tP4ssw0rd!_2026@redis:6379/0

# ── Security & Secrets ────────────────────────────────────────────────────
JWT_SECRET_KEY={jwt_secret}
K1_SECRET_BACKEND=vault
K1_ENABLE_BOOTSTRAP_AUTH_BUILD=true
K1_DEV_CERT_AUTH_ENABLED=true
K1_DEV_AUTH_CA_PATH=dev-certs/ca.crt.pem

# ── Proxy / Whonix Configuration ─────────────────────────────────────────
HTTP_PROXY={http_proxy}
HTTPS_PROXY={https_proxy}
K1_USE_DOCKER_SANDBOX=true

# ── Application Settings ──────────────────────────────────────────────────
DEBUG_MODE=true
ENVIRONMENT=development
LOG_LEVEL=INFO
"""

    with open(env_path, 'w') as f:
        f.write(env_content)

    # Summary
    print("\n" + "="*60)
    print("  Configuration complete!")
    print("="*60)
    configured_names = [label for label, _ in configured] or ["(none)"]
    print(f"  Primary provider : {primary_provider}")
    print(f"  Primary model    : {primary_model}")
    print(f"  Keys configured  : {', '.join(configured_names)}")
    if fallback_providers:
        print(f"  Fallback chain   : {fallback_providers}")
    print()
    print("  Run './k1 start' to launch the platform.")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nConfiguration cancelled.")
        sys.exit(1)
