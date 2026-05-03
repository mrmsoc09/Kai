"""
Security utilities for sandboxing and input validation.
"""
import hashlib
import re
import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Set

from .models import ScriptLanguage


class SecurityValidator:
    """Validates scripts for dangerous patterns before execution."""
    
    DANGEROUS_PATTERNS = {
        ScriptLanguage.PYTHON: [
            r'__import__\s*\(\s*["\']os["\']',
            r'subprocess\..*shell\s*=\s*True',
            r'eval\s*\(',
            r'exec\s*\(',
            r'compile\s*\(',
            r'import\s+pty',
            r'os\.system',
            r'os\.popen',
        ],
        ScriptLanguage.BASH: [
            r'>\s*/dev/',
            r'rm\s+-rf\s+/',
            r':(){ :|:& };:',  # Fork bomb
            r'curl.*\|.*bash',
            r'wget.*\|.*sh',
            r'>\s*/etc/',
            r'mkfs\.',
            r'dd\s+if=.*of=/dev/',
        ],
        ScriptLanguage.GO: [
            r'os\.Exec\s*\(',
            r'syscall\.Exec',
        ]
    }
    
    @classmethod
    def validate_script(cls, content: str, language: ScriptLanguage) -> tuple[bool, List[str]]:
        """Check script for dangerous patterns."""
        violations = []
        patterns = cls.DANGEROUS_PATTERNS.get(language, [])
        
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                violations.append(f"Potentially dangerous pattern detected: {pattern}")
        
        return len(violations) == 0, violations
    
    @staticmethod
    def calculate_checksum(content: str) -> str:
        """Calculate SHA-256 checksum of script content."""
        return hashlib.sha256(content.encode()).hexdigest()


class Sandbox:
    """Creates isolated execution environment."""
    
    def __init__(self, base_path: str = "/tmp/orchestrator_sandbox"):
        self.base_path = Path(base_path)
        self.sandbox_id = hashlib.md5(os.urandom(16)).hexdigest()[:8]
        self.sandbox_path = self.base_path / self.sandbox_id
        self.created = False
        
    def create(self) -> Path:
        """Create sandbox directory structure."""
        self.sandbox_path.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.sandbox_path / "workspace").mkdir()
        (self.sandbox_path / "output").mkdir()
        (self.sandbox_path / "tmp").mkdir()
        
        self.created = True
        return self.sandbox_path
    
    def cleanup(self):
        """Remove sandbox directory."""
        if self.created and self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path)
            self.created = False
    
    def write_script(self, filename: str, content: str) -> Path:
        """Write script to sandbox workspace."""
        if not self.created:
            self.create()
        
        script_path = self.sandbox_path / "workspace" / filename
        script_path.write_text(content)
        return script_path
    
    def __enter__(self):
        self.create()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
