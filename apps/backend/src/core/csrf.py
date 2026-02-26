"""
CSRF (Cross-Site Request Forgery) Token Management
Generates and validates CSRF tokens for state-changing requests.
"""

import secrets
from typing import Dict, Optional
from datetime import datetime, timedelta


class CSRFTokenManager:
    """
    CSRF token generation and validation.

    Maintains a mapping of session_id -> (token, expiration_time).
    Tokens are validated against stored values using constant-time comparison.
    """

    def __init__(self, token_expiry_minutes: int = 60):
        """
        Initialize CSRF token manager.

        Args:
            token_expiry_minutes: How long tokens are valid (default 60 minutes)
        """
        self.tokens: Dict[str, tuple] = {}  # {session_id: (token, expiry_time)}
        self.token_expiry_minutes = token_expiry_minutes

    def generate_token(self, session_id: str) -> str:
        """
        Generate a new CSRF token for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            A cryptographically secure random token (32 bytes, URL-safe)
        """
        # Generate secure random token
        token = secrets.token_urlsafe(32)

        # Store with expiration
        expiry = datetime.now() + timedelta(minutes=self.token_expiry_minutes)
        self.tokens[session_id] = (token, expiry)

        return token

    def validate_token(self, session_id: str, token: str) -> bool:
        """
        Validate a CSRF token against stored value.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            session_id: Session identifier
            token: Token to validate

        Returns:
            True if token is valid and not expired, False otherwise
        """
        if session_id not in self.tokens:
            return False

        stored_token, expiry = self.tokens[session_id]

        # Check expiration
        if datetime.now() > expiry:
            del self.tokens[session_id]
            return False

        # Use constant-time comparison to prevent timing attacks
        try:
            return secrets.compare_digest(stored_token, token)
        except (TypeError, AttributeError):
            return False

    def invalidate_token(self, session_id: str) -> None:
        """
        Explicitly invalidate a CSRF token.

        Args:
            session_id: Session to invalidate token for
        """
        if session_id in self.tokens:
            del self.tokens[session_id]

    def cleanup_expired(self) -> int:
        """
        Remove expired tokens from storage.

        Returns:
            Number of tokens cleaned up
        """
        now = datetime.now()
        expired_sessions = [
            sid for sid, (_, expiry) in self.tokens.items()
            if expiry < now
        ]

        for sid in expired_sessions:
            del self.tokens[sid]

        return len(expired_sessions)

    def get_token_info(self, session_id: str) -> Optional[Dict]:
        """
        Get information about a session's CSRF token.

        Args:
            session_id: Session identifier

        Returns:
            Dict with token info or None if not found
        """
        if session_id not in self.tokens:
            return None

        token, expiry = self.tokens[session_id]
        return {
            "session_id": session_id,
            "token_length": len(token),
            "expires_at": expiry.isoformat(),
            "expired": datetime.now() > expiry,
        }


# Global instance
csrf_manager = CSRFTokenManager()

# List of endpoints that should skip CSRF validation
# Note: Adding /detection/nuclei/scan allows headless agents/CLI to trigger scans
# without providing a CSRF token.
CSRF_EXEMPT_ENDPOINTS = [
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/login",
    "/auth/logout",
    "/auth/refresh",
    "/detection/nuclei/scan",
]

# HTTP methods that don't need CSRF protection (idempotent)
CSRF_EXEMPT_METHODS = ["GET", "HEAD", "OPTIONS", "TRACE"]
