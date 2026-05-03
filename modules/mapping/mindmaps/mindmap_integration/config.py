"""
Configuration management for Mindmap Integration System.
"""

import os
from typing import Dict, Any
from pathlib import Path


class Config:
    """
    Configuration settings for the mindmap system.
    """
    
    def __init__(self):
        self.output_dir = os.getenv("MINDMAP_OUTPUT_DIR", "./output")
        self.default_format = os.getenv("MINDMAP_DEFAULT_FORMAT", "mermaid")
        self.ai_enhancement = os.getenv("MINDMAP_AI_ENHANCE", "true").lower() == "true"
        self.max_depth = int(os.getenv("MINDMAP_MAX_DEPTH", "5"))
        self.exclude_patterns = os.getenv("MINDMAP_EXCLUDE", ".git,node_modules,__pycache__").split(",")
        
        # AI Configuration
        self.brainstorm_depth = int(os.getenv("BRAINSTORM_DEPTH", "3"))
        self.security_analysis = os.getenv("SECURITY_ANALYSIS", "true").lower() == "true"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "output_dir": self.output_dir,
            "default_format": self.default_format,
            "ai_enhancement": self.ai_enhancement,
            "max_depth": self.max_depth,
            "exclude_patterns": self.exclude_patterns,
            "brainstorm_depth": self.brainstorm_depth,
            "security_analysis": self.security_analysis
        }
    
    @classmethod
    def from_file(cls, path: str) -> "Config":
        """Load configuration from JSON file."""
        import json
        config = cls()
        
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        return config
