"""
Validation utilities for content data.
"""

import re
from typing import Optional
from urllib.parse import urlparse


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email string
        
    Returns:
        True if valid
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone: str, country: str = "US") -> bool:
    """
    Validate phone number format.
    
    Args:
        phone: Phone string
        country: Country code
        
    Returns:
        True if valid
    """
    if country == "US":
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
        return len(cleaned) == 10 and cleaned.isdigit()
    return True


def validate_url(url: str) -> bool:
    """
    Validate URL format.
    
    Args:
        url: URL string
        
    Returns:
        True if valid
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def validate_naics_code(code: str) -> bool:
    """
    Validate NAICS code format.
    
    Args:
        code: NAICS code string
        
    Returns:
        True if valid
    """
    # NAICS codes are 2-6 digits
    cleaned = code.strip()
    return cleaned.isdigit() and 2 <= len(cleaned) <= 6


def validate_cage_code(code: str) -> bool:
    """
    Validate CAGE code format (5 characters).
    
    Args:
        code: CAGE code
        
    Returns:
        True if valid
    """
    return len(code.strip()) == 5 and code.strip().isalnum()
