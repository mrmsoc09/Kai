"""Common permutation patterns."""

from typing import List, Set, Callable
import itertools
import re


class PatternLibrary:
    """Library of common permutation patterns."""
    
    @staticmethod
    def leet_speak(word: str) -> Set[str]:
        """Generate leet speak variations."""
        leet_map = {
            'a': ['a', 'A', '@', '4'],
            'b': ['b', 'B', '8'],
            'e': ['e', 'E', '3'],
            'g': ['g', 'G', '9', '6'],
            'i': ['i', 'I', '1', '!'],
            'o': ['o', 'O', '0'],
            's': ['s', 'S', '$', '5'],
            't': ['t', 'T', '7'],
            'z': ['z', 'Z', '2'],
        }
        
        if not word:
            return {word}
            
        # Generate combinations
        options = [leet_map.get(c.lower(), [c]) for c in word]
        combinations = itertools.product(*options)
        
        return {''.join(combo) for combo in combinations}
    
    @staticmethod
    def year_appendices(word: str, years: List[int] = None) -> Set[str]:
        """Append common years."""
        if years is None:
            years = list(range(2020, 2026))
            
        results = {word}
        for year in years:
            results.add(f"{word}{year}")
            results.add(f"{word}_{year}")
            results.add(f"{word}{str(year)[-2:]}")  # Short year
        return results
    
    @staticmethod
    def special_characters(word: str, chars: List[str] = None) -> Set[str]:
        """Append special characters."""
        if chars is None:
            chars = ['!', '@', '#', '$', '%', '*', '?', '.']
            
        results = {word}
        for char in chars:
            results.add(f"{word}{char}")
            results.add(f"{char}{word}")
        return results
    
    @staticmethod
    def case_variations(word: str) -> Set[str]:
        """Generate case variations."""
        return {
            word.lower(),
            word.upper(),
            word.capitalize(),
            word.swapcase(),
        }
    
    @staticmethod
    def number_sequences(word: str, max_num: int = 100) -> Set[str]:
        """Append number sequences."""
        results = {word}
        for i in range(max_num):
            results.add(f"{word}{i}")
            results.add(f"{word}{i:02d}")
            if i < 10:
                results.add(f"{word}{i}!")
        return results
    
    @staticmethod
    def keyboard_patterns(word: str) -> Set[str]:
        """Append keyboard walk patterns."""
        patterns = ['123', '1234', '12345', 'qwe', 'qwerty', 'asd', 'zxc', 'qaz', 'wsx']
        results = {word}
        for pattern in patterns:
            results.add(f"{word}{pattern}")
            results.add(f"{pattern}{word}")
        return results
