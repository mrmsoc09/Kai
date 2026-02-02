"""
CORS Configuration Management
Loads CORS settings from environment and provides validated configuration
"""

import os
from typing import List, Dict, Any


def get_cors_config() -> Dict[str, Any]:
    """
    Load and validate CORS configuration from environment variables.

    Returns:
        Dictionary with CORS middleware configuration
    """

    # Load allowed origins from env (comma-separated)
    allowed_origins_str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8081,http://localhost:3000"
    )

    # Parse and validate origins
    origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

    if not origins:
        raise ValueError("CORS_ALLOWED_ORIGINS is empty")

    # Never allow wildcard with credentials
    if "*" in origins and os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true":
        raise ValueError(
            "Cannot allow wildcard origin ('*') with credentials. "
            "Set CORS_ALLOW_CREDENTIALS=false or use explicit origins."
        )

    # Load other CORS settings
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"

    return {
        "allow_origins": origins,
        "allow_credentials": allow_credentials,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
        "expose_headers": [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "X-Request-ID",
        ],
        "max_age": 3600,  # 1 hour
    }


def print_cors_config() -> None:
    """Print CORS configuration for debugging."""
    config = get_cors_config()
    print("\n📋 CORS Configuration:")
    print(f"  Allowed Origins ({len(config['allow_origins'])}):")
    for origin in config["allow_origins"]:
        print(f"    - {origin}")
    print(f"  Allow Credentials: {config['allow_credentials']}")
    print(f"  Allowed Methods: {', '.join(config['allow_methods'])}")
    print(f"  Max Age: {config['max_age']}s")
    print()
