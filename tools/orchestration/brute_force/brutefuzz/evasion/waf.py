"""WAF evasion techniques"""
import random
import base64
import urllib.parse
from typing import List


class WAFEvasion:
    """Web Application Firewall evasion techniques"""
    
    def __init__(self, config):
        self.config = config
        self.techniques = [
            self._url_encode,
            self._double_url_encode,
            self._base64_encode,
            self._case_randomization,
            self._comment_insertion,
            self._unicode_normalize,
        ]
        
    def obfuscate(self, payload: str) -> str:
        """Apply random evasion technique"""
        if not self.config.waf_evasion_enabled:
            return payload
            
        # Randomly select technique based on payload content
        technique = random.choice(self.techniques)
        return technique(payload)
    
    def _url_encode(self, payload: str) -> str:
        """Standard URL encoding"""
        return urllib.parse.quote(payload, safe='')
    
    def _double_url_encode(self, payload: str) -> str:
        """Double URL encoding"""
        return urllib.parse.quote(urllib.parse.quote(payload, safe=''), safe='')
    
    def _base64_encode(self, payload: str) -> str:
        """Base64 encoding with optional markers"""
        encoded = base64.b64encode(payload.encode()).decode()
        return encoded
    
    def _case_randomization(self, payload: str) -> str:
        """Random case for SQL keywords"""
        sql_keywords = ['select', 'union', 'from', 'where', 'and', 'or', 'insert', 'delete']
        result = payload
        for keyword in sql_keywords:
            if keyword.lower() in result.lower():
                # Randomize case
                new_keyword = ''.join(random.choice([c.upper(), c.lower()]) for c in keyword)
                result = result.replace(keyword, new_keyword, 1)
        return result
    
    def _comment_insertion(self, payload: str) -> str:
        """Insert SQL comments to break signatures"""
        # Insert /**/ in SQL contexts
        chars = list(payload)
        positions = random.sample(range(1, len(chars)), min(2, len(chars)-1))
        for pos in sorted(positions, reverse=True):
            chars.insert(pos, '/**/')
        return ''.join(chars)
    
    def _unicode_normalize(self, payload: str) -> str:
        """Unicode normalization evasion"""
        # Replace some chars with unicode equivalents
        replacements = {
            'a': '\u0430',  # Cyrillic а
            'e': '\u0435',  # Cyrillic е
            'o': '\u043e',  # Cyrillic о
            'p': '\u0440',  # Cyrillic р
        }
        result = payload
        for orig, repl in replacements.items():
            if random.random() > 0.5:
                result = result.replace(orig, repl, 1)
        return result
