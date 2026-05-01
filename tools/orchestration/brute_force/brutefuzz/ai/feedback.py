"""
AI-driven feedback loop for intelligent payload mutation
Implements Kimi k2.5 logic for adaptive fuzzing
"""
import random
import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class PayloadSignature:
    """Signature of a successful payload"""
    structure: str
    length: int
    special_chars: Set[str]
    entropy: float
    context: str


class AIFeedbackLoop:
    """
    Intelligent feedback system that learns from successful payloads
    and guides mutation strategies
    """
    
    def __init__(self, config):
        self.config = config
        self.successful_patterns: List[PayloadSignature] = []
        self.failure_patterns: Set[str] = set()
        self.context_success: Dict[str, int] = defaultdict(int)
        self.mutation_history: List[str] = []
        
        # Learning parameters
        self.learning_rate = 0.1
        self.exploration_rate = 0.2
        
    def report_success(self, payload: str, response_data: Optional[str]):
        """Learn from successful payload"""
        signature = self._analyze_payload(payload)
        self.successful_patterns.append(signature)
        
        # Extract context from response
        context = self._extract_context(response_data)
        self.context_success[context] += 1
        
        # Reduce exploration as we learn
        self.exploration_rate *= 0.99
        
    def report_failure(self, payload: str):
        """Record failed pattern to avoid"""
        self.failure_patterns.add(self._normalize(payload))
        
    def mutate_payload(self, payload: str) -> str:
        """
        Apply intelligent mutation based on learned patterns
        Uses Kimi k2.5 logic: context-aware, structure-preserving mutations
        """
        if not self.successful_patterns:
            return self._random_mutation(payload)
            
        # Decide: exploit known patterns or explore
        if random.random() < self.exploration_rate:
            return self._exploratory_mutation(payload)
        else:
            return self._exploitative_mutation(payload)
    
    def _analyze_payload(self, payload: str) -> PayloadSignature:
        """Extract features from payload"""
        # Calculate simple entropy
        entropy = self._calculate_entropy(payload)
        
        # Extract structure (alpha, digit, special patterns)
        structure = re.sub(r'[a-zA-Z]', 'A', payload)
        structure = re.sub(r'\d', '9', structure)
        
        special_chars = set(c for c in payload if not c.isalnum())
        
        return PayloadSignature(
            structure=structure,
            length=len(payload),
            special_chars=special_chars,
            entropy=entropy,
            context=""
        )
    
    def _calculate_entropy(self, s: str) -> float:
        """Calculate Shannon entropy"""
        if not s:
            return 0.0
        prob = [float(s.count(c)) / len(s) for c in dict.fromkeys(list(s))]
        entropy = - sum([p * (lambda x: 0 if x == 0 else x.__import__('math').log2(x))(p) for p in prob])
        return entropy
    
    def _extract_context(self, response: Optional[str]) -> str:
        """Extract context hints from response"""
        if not response:
            return "unknown"
        # Simple context extraction
        if "error" in response.lower():
            return "error_page"
        elif "welcome" in response.lower():
            return "success_page"
        return "generic"
    
    def _normalize(self, payload: str) -> str:
        """Normalize payload for pattern matching"""
        return payload.lower().strip()
    
    def _random_mutation(self, payload: str) -> str:
        """Basic random mutation"""
        mutations = [
            lambda x: x + str(random.randint(0, 999)),
            lambda x: x + random.choice(['!', '@', '#', '$']),
            lambda x: x.capitalize(),
            lambda x: x.upper(),
        ]
        return random.choice(mutations)(payload)
    
    def _exploratory_mutation(self, payload: str) -> str:
        """Try novel mutations"""
        # Insert random special chars
        chars = list(payload)
        pos = random.randint(0, len(chars))
        chars.insert(pos, random.choice(['<', '>', '"', "'", '\\', '/']))
        return ''.join(chars)
    
    def _exploitative_mutation(self, payload: str) -> str:
        """Mutate based on successful patterns"""
        if not self.successful_patterns:
            return payload
            
        # Find most successful pattern
        best_pattern = max(self.successful_patterns, 
                          key=lambda x: self.context_success[x.context])
        
        # Adapt payload to match successful structure
        mutated = payload
        
        # Adjust length towards successful length
        if len(mutated) < best_pattern.length:
            mutated += 'X' * (best_pattern.length - len(mutated))
        elif len(mutated) > best_pattern.length:
            mutated = mutated[:best_pattern.length]
            
        # Add successful special chars
        if best_pattern.special_chars:
            char = random.choice(list(best_pattern.special_chars))
            pos = random.randint(0, len(mutated))
            mutated = mutated[:pos] + char + mutated[pos:]
            
        return mutated
