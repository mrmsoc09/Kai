from __future__ import annotations
from typing import Dict, Any

class Mailer:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def preview(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        return {'to': to, 'subject': subject, 'body': body, 'enabled': self.enabled}

    def send(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        if not self.enabled:
            return {'status': 'blocked', 'reason': 'email_sending_disabled'}
        # Placeholder; real implementation would use SMTP creds from Vault.
        return {'status': 'sent', 'to': to}
