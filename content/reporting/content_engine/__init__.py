"""
Content Generation Engine (CGE)
A modular system for generating intelligence reports, contracting documents,
threat intelligence, e-books, guides, and playbooks.
"""

__version__ = "0.1.0"
__author__ = "CGE Team"

from content_engine.generators.intelligence import IntelligenceReportGenerator
from content_engine.generators.contracting import ContractingGenerator
from content_engine.generators.threat_intel import ThreatIntelGenerator
from content_engine.generators.ebook import EbookGenerator
from content_engine.generators.guide import GuideGenerator

__all__ = [
    "IntelligenceReportGenerator",
    "ContractingGenerator", 
    "ThreatIntelGenerator",
    "EbookGenerator",
    "GuideGenerator",
]
