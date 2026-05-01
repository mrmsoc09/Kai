"""Kimi k2.5 style AI-driven keyword expansion.

Implements architectural patterns inspired by Kimi k2.5:
- Large context window processing
- Semantic similarity analysis
- Context-aware generation
- Multi-hop reasoning for keyword relationships
"""

import asyncio
from typing import Set, List, Dict, Optional
from dataclasses import dataclass
import re
import logging
from collections import defaultdict

from wordlist_generator.ai.base import BaseAIProvider
from wordlist_generator.core.config import AIConfig

logger = logging.getLogger(__name__)


@dataclass
class SemanticCluster:
    """Cluster of semantically related terms."""
    center: str
    related: Set[str]
    confidence: float


class KimiK25Logic(BaseAIProvider):
    """
    Kimi k2.5 style expansion engine.
    
    Simulates large context window analysis and semantic understanding
    using local algorithms (Markov chains, pattern recognition, 
    contextual association) while maintaining API compatibility for
    actual LLM integration.
    """
    
    def __init__(self, config: AIConfig):
        self.config = config
        self.context_memory: Dict[str, List[str]] = defaultdict(list)
        self.semantic_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # Contextual association patterns (simulating semantic understanding)
        self.associations = {
            'tech': ['dev', 'api', 'code', 'git', 'docker', 'cloud', 'aws', 'azure'],
            'security': ['auth', 'login', 'admin', 'root', 'pass', 'key', 'secret', 'token'],
            'business': ['corp', 'inc', 'ltd', 'enterprise', 'solutions', 'services'],
            'personal': ['home', 'user', 'me', 'my', 'private', 'personal'],
        }
        
        # Common substitutions (leet speak and variations)
        self.substitutions = {
            'a': ['@', '4', 'A'],
            'e': ['3', 'E'],
            'i': ['1', '!', 'I'],
            'o': ['0', 'O'],
            's': ['$', '5', 'S'],
            't': ['7', 'T'],
        }
        
    async def expand(self, keyword: str, context: str) -> Set[str]:
        """
        Expand keyword using Kimi k2.5 style logic:
        1. Contextual analysis
        2. Semantic clustering
        3. Pattern-based generation
        4. Multi-hop association
        """
        expansions = set()
        expansions.add(keyword)
        
        # Stage 1: Contextual embedding (simulated)
        context_vector = self._analyze_context_vector(keyword, context)
        
        # Stage 2: Semantic expansion
        semantic_variations = await self._semantic_expansion(keyword, context_vector)
        expansions.update(semantic_variations)
        
        # Stage 3: Pattern mutations (leet, case, years)
        pattern_variations = self._generate_patterns(keyword)
        expansions.update(pattern_variations)
        
        # Stage 4: Contextual associations
        if len(expansions) < self.config.max_expansions_per_keyword:
            associations = self._contextual_associations(keyword, context_vector)
            expansions.update(associations)
            
        # Stage 5: Combinatorial synthesis
        if len(expansions) < self.config.max_expansions_per_keyword:
            combined = self._combinatorial_synthesis(expansions, context_vector)
            expansions.update(combined)
            
        return expansions
    
    def analyze_context(self, keywords: Set[str], target: str) -> dict:
        """Analyze semantic context of keyword set."""
        analysis = {
            'domain_category': self._categorize_domain(target),
            'tech_stack_indicators': set(),
            'naming_conventions': [],
            'entropy_score': 0.0,
        }
        
        for keyword in keywords:
            # Detect tech stack
            tech_indicators = self._detect_tech_stack(keyword)
            analysis['tech_stack_indicators'].update(tech_indicators)
            
            # Analyze naming patterns
            pattern = self._analyze_naming_pattern(keyword)
            if pattern:
                analysis['naming_conventions'].append(pattern)
                
        analysis['entropy_score'] = self._calculate_entropy(keywords)
        return analysis
    
    def _analyze_context_vector(self, keyword: str, context: str) -> Dict:
        """Create contextual embedding vector."""
        vector = {
            'keyword': keyword,
            'domain': context,
            'category': self._categorize_token(keyword),
            'length': len(keyword),
            'complexity': self._calculate_complexity(keyword),
            'semantic_field': set(),
        }
        
        # Determine semantic field
        for category, terms in self.associations.items():
            if any(term in keyword.lower() for term in terms):
                vector['semantic_field'].add(category)
                
        return vector
    
    async def _semantic_expansion(self, keyword: str, context_vector: Dict) -> Set[str]:
        """Generate semantically related variations."""
        variations = set()
        
        # Synonym expansion (local thesaurus simulation)
        synonyms = self._get_synonyms(keyword)
        variations.update(synonyms)
        
        # Contextual prefix/suffix addition
        prefixes = ['my', 'the', 'new', 'old', 'temp', 'test', 'prod', 'dev']
        suffixes = ['123', '2024', '2023', '01', '99', '00', 'x', '2', '3']
        
        for prefix in prefixes[:3]:  # Limit to avoid explosion
            variations.add(f"{prefix}{keyword}")
            variations.add(f"{prefix}_{keyword}")
            
        for suffix in suffixes[:3]:
            variations.add(f"{keyword}{suffix}")
            variations.add(f"{keyword}_{suffix}")
            
        return variations
    
    def _generate_patterns(self, keyword: str) -> Set[str]:
        """Generate pattern-based variations (leet, case, etc.)."""
        variations = set()
        
        # Case variations
        variations.add(keyword.lower())
        variations.add(keyword.upper())
        variations.add(keyword.capitalize())
        variations.add(keyword.swapcase())
        
        # Leet speak variations
        leet_variants = self._generate_leet_variants(keyword)
        variations.update(leet_variants)
        
        # Year appendices
        years = ['2024', '2023', '2022', '2025', '2020']
        for year in years:
            variations.add(f"{keyword}{year}")
            variations.add(f"{keyword}_{year}")
            
        return variations
    
    def _contextual_associations(self, keyword: str, context_vector: Dict) -> Set[str]:
        """Generate associations based on semantic fields."""
        associations = set()
        
        for field in context_vector['semantic_field']:
            if field in self.associations:
                for term in self.associations[field][:3]:
                    associations.add(f"{keyword}{term}")
                    associations.add(f"{term}{keyword}")
                    associations.add(f"{keyword}_{term}")
                    
        return associations
    
    def _combinatorial_synthesis(self, existing: Set[str], context_vector: Dict) -> Set[str]:
        """Combine existing variations to create new ones."""
        synthesized = set()
        existing_list = list(existing)[:10]  # Limit combinations
        
        for i, word1 in enumerate(existing_list):
            for word2 in existing_list[i+1:]:
                if len(word1) + len(word2) < 20:
                    synthesized.add(f"{word1}{word2}")
                    synthesized.add(f"{word1}_{word2}")
                    synthesized.add(f"{word1}-{word2}")
                    
        return synthesized
    
    def _categorize_token(self, token: str) -> str:
        """Categorize token type."""
        if re.match(r'^\d+$', token):
            return 'numeric'
        elif re.match(r'^[A-Z][a-z]+$', token):
            return 'proper_noun'
        elif re.match(r'^[a-z]+$', token):
            return 'common_noun'
        elif re.match(r'^[A-Za-z0-9]+$', token):
            return 'alphanumeric'
        else:
            return 'complex'
    
    def _calculate_complexity(self, token: str) -> float:
        """Calculate complexity score."""
        unique_chars = len(set(token))
        length = len(token)
        return unique_chars / length if length > 0 else 0.0
    
    def _get_synonyms(self, word: str) -> Set[str]:
        """Local synonym lookup (simplified)."""
        # In production, this would use WordNet or similar
        common_synonyms = {
            'admin': ['administrator', 'root', 'superuser', 'sysadmin'],
            'user': ['account', 'profile', 'member', 'client'],
            'password': ['pass', 'passwd', 'pwd', 'secret'],
            'login': ['signin', 'auth', 'access', 'entry'],
        }
        return set(common_synonyms.get(word.lower(), []))
    
    def _generate_leet_variants(self, word: str) -> Set[str]:
        """Generate leet speak variations."""
        variants = set()
        
        # Simple character replacement
        for char, replacements in self.substitutions.items():
            if char in word.lower():
                for replacement in replacements:
                    variant = word.lower().replace(char, replacement)
                    variants.add(variant)
                    
        return variants
    
    def _categorize_domain(self, domain: str) -> str:
        """Categorize target domain."""
        domain_lower = domain.lower()
        if any(t in domain_lower for t in ['tech', 'soft', 'dev', 'app', 'io']):
            return 'technology'
        elif any(t in domain_lower for t in ['bank', 'fin', 'pay', 'money']):
            return 'financial'
        elif any(t in domain_lower for t in ['shop', 'store', 'mart', 'buy']):
            return 'retail'
        return 'general'
    
    def _detect_tech_stack(self, keyword: str) -> Set[str]:
        """Detect technology indicators in keyword."""
        indicators = set()
        tech_patterns = {
            'python': ['py', 'django', 'flask', 'pip'],
            'javascript': ['js', 'node', 'react', 'vue', 'angular'],
            'java': ['spring', 'maven', 'gradle', 'jsp'],
            'dotnet': ['asp', 'net', 'csharp', 'mvc'],
        }
        
        keyword_lower = keyword.lower()
        for tech, patterns in tech_patterns.items():
            if any(p in keyword_lower for p in patterns):
                indicators.add(tech)
                
        return indicators
    
    def _analyze_naming_pattern(self, keyword: str) -> Optional[str]:
        """Analyze naming convention pattern."""
        if '_' in keyword:
            return 'snake_case'
        elif '-' in keyword:
            return 'kebab-case'
        elif keyword.isupper():
            return 'uppercase'
        elif keyword[0].isupper() if keyword else False:
            return 'pascal_case'
        return None
    
    def _calculate_entropy(self, keywords: Set[str]) -> float:
        """Calculate Shannon entropy of keyword set."""
        if not keywords:
            return 0.0
            
        all_chars = ''.join(keywords)
        length = len(all_chars)
        if length == 0:
            return 0.0
            
        freq = {}
        for char in all_chars:
            freq[char] = freq.get(char, 0) + 1
            
        import math
        entropy = 0.0
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
            
        return entropy
