"""
Formatting utilities for content generation.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def format_classification(classification: str, banner_width: int = 60) -> str:
    """
    Format classification level with standard banner.
    
    Args:
        classification: Classification string
        banner_width: Width of the banner
        
    Returns:
        Formatted banner string
    """
    text = f" {classification.upper()} "
    padding = (banner_width - len(text)) // 2
    banner = "=" * padding + text + "=" * padding
    if len(banner) < banner_width:
        banner += "=" * (banner_width - len(banner))
    return banner


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a string to be safe for use as a filename.
    
    Args:
        filename: Original filename
        replacement: Character to replace invalid chars with
        
    Returns:
        Safe filename
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', replacement, filename)
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized.strip()


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Input text
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def word_count(text: str) -> int:
    """
    Count words in text.
    
    Args:
        text: Input text
        
    Returns:
        Word count
    """
    return len(text.split())


def format_currency(amount: float, currency: str = "$") -> str:
    """
    Format currency amount.
    
    Args:
        amount: Numeric amount
        currency: Currency symbol
        
    Returns:
        Formatted string
    """
    return f"{currency}{amount:,.2f}"


def generate_header(metadata: dict, doc_type: str = "REPORT") -> str:
    """
    Generate a standard document header.
    
    Args:
        metadata: Document metadata
        doc_type: Type of document
        
    Returns:
        Formatted header string
    """
    lines = [
        "=" * 60,
        f"{doc_type}: {metadata.get('title', 'UNTITLED')}",
        f"Date: {metadata.get('created_at', datetime.now().isoformat())}",
        f"Author: {metadata.get('author', 'Unknown')}",
        "=" * 60,
        ""
    ]
    return "\n".join(lines)
