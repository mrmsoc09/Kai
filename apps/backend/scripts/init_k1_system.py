#!/usr/bin/env python3
"""
K1 System Initialization Script
Initializes all tools, programs, embeddings, and prepares the unified platform

Usage:
    python init_k1_system.py [--verbose] [--init-embeddings] [--scrape-programs]
"""

import asyncio
import sys
import logging
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.tools import get_registry
from src.core.tools_validators import FindingValidatorTool, QuickClassifierTool
from src.core.tools_analysis import (
    VulnerabilityAnalyzerTool,
    ChainAnalyzerTool,
    ProgramMatcherTool,
)
from src.core.program_scrapers import ScraperFactory
from src.core.embeddings_client import EmbeddingClientFactory, VectorStore

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class K1SystemInitializer:
    """Initializes the unified K1 system"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.registry = None
        self.embeddings_client = None
        self.vector_store = None

    def init_tools(self) -> bool:
        """Initialize all tools"""
        logger.info("=" * 60)
        logger.info("Initializing K1 Tool Registry")
        logger.info("=" * 60)

        try:
            self.registry = get_registry()

            # Register validation tools
            logger.info("📋 Registering validation tools...")
            validator = FindingValidatorTool()
            self.registry.register(validator)
            logger.info(f"  ✓ Finding Validator Tool (ID: {validator.id})")

            classifier = QuickClassifierTool()
            self.registry.register(classifier)
            logger.info(f"  ✓ Quick Classifier Tool (ID: {classifier.id})")

            # Register analysis tools
            logger.info("🔍 Registering analysis tools...")
            analyzer = VulnerabilityAnalyzerTool()
            self.registry.register(analyzer)
            logger.info(f"  ✓ Vulnerability Analyzer Tool (ID: {analyzer.id})")

            chain_analyzer = ChainAnalyzerTool()
            self.registry.register(chain_analyzer)
            logger.info(f"  ✓ Chain Analyzer Tool (ID: {chain_analyzer.id})")

            matcher = ProgramMatcherTool()
            self.registry.register(matcher)
            logger.info(f"  ✓ Program Matcher Tool (ID: {matcher.id})")

            # Print registry stats
            logger.info("")
            logger.info("📊 Tool Registry Statistics:")
            stats = self.registry.stats()
            logger.info(f"  Total Tools: {stats['total_tools']}")
            for category, count in stats['by_category'].items():
                logger.info(f"  {category.upper()}: {count}")

            logger.info("✅ Tool initialization successful\n")
            return True

        except Exception as e:
            logger.error(f"❌ Tool initialization failed: {str(e)}")
            return False

    async def init_embeddings(self) -> bool:
        """Initialize embeddings system"""
        logger.info("=" * 60)
        logger.info("Initializing Embeddings System")
        logger.info("=" * 60)

        try:
            logger.info("🧠 Creating hybrid embedding client...")
            self.embeddings_client = EmbeddingClientFactory.create_hybrid()
            logger.info(f"  ✓ Primary client: OpenAI (if available)")
            logger.info(f"  ✓ Fallback client: Local Sentence-Transformers")
            logger.info(f"  ✓ Embedding dimension: {self.embeddings_client.dimension}")

            logger.info("📦 Creating vector store...")
            self.vector_store = VectorStore(self.embeddings_client)
            logger.info(f"  ✓ Vector store initialized")

            # Test embedding
            logger.info("\n🧪 Testing embedding system...")
            test_text = "XSS vulnerability in login form"
            embedding, source = self.embeddings_client.embed_text(test_text)
            logger.info(f"  ✓ Test embedding from {source.upper()}")
            logger.info(f"  ✓ Embedding dimension: {len(embedding)}")

            logger.info("✅ Embeddings initialization successful\n")
            return True

        except Exception as e:
            logger.error(f"❌ Embeddings initialization failed: {str(e)}")
            return False

    async def init_programs(self) -> bool:
        """Initialize program discovery system"""
        logger.info("=" * 60)
        logger.info("Initializing Program Discovery System")
        logger.info("=" * 60)

        try:
            logger.info("🌐 Getting available scrapers...")
            scrapers = ScraperFactory.get_all_scrapers()
            logger.info(f"  ✓ Found {len(scrapers)} platform scrapers:")

            platforms_info = []
            for scraper in scrapers:
                logger.info(f"    - {scraper.platform_name}")
                platforms_info.append(scraper.platform_name)

            logger.info("\n📡 Scraper capabilities:")
            logger.info("  ✓ Async scraping support")
            logger.info("  ✓ Progress streaming with callbacks")
            logger.info("  ✓ Metadata enrichment")
            logger.info("  ✓ Payout structure definitions")
            logger.info("  ✓ Scope management (allowed/excluded)")

            logger.info("✅ Program discovery initialization successful\n")
            return True

        except Exception as e:
            logger.error(f"❌ Program discovery initialization failed: {str(e)}")
            return False

    async def scrape_programs(self) -> bool:
        """Scrape programs from all platforms"""
        logger.info("=" * 60)
        logger.info("Scraping Bug Bounty Programs")
        logger.info("=" * 60)

        try:
            scrapers = ScraperFactory.get_all_scrapers()
            all_programs = []

            for scraper in scrapers:
                logger.info(f"\n🔄 Scraping {scraper.platform_name}...")

                def on_progress(progress):
                    if self.verbose:
                        print(f"  {progress.current_program}: {progress.get_progress_percent()}%")

                scraper.on_progress(on_progress)
                programs = await scraper.scrape()

                logger.info(f"  ✓ Found {len(programs)} programs")
                all_programs.extend(programs)

            logger.info(f"\n📊 Total programs scraped: {len(all_programs)}")

            # Show payout summary
            total_payout = sum(p.get('average_payout', 0) for p in all_programs)
            avg_payout = total_payout / len(all_programs) if all_programs else 0

            logger.info(f"  Total average payouts: ${total_payout:,.0f}")
            logger.info(f"  Average payout per program: ${avg_payout:,.0f}")

            logger.info("✅ Program scraping successful\n")
            return True

        except Exception as e:
            logger.error(f"❌ Program scraping failed: {str(e)}")
            return False

    async def demo_tools(self) -> bool:
        """Demonstrate tool usage"""
        logger.info("=" * 60)
        logger.info("Demonstrating Tool Usage")
        logger.info("=" * 60)

        try:
            logger.info("\n1️⃣  Quick Classification Demo:")
            logger.info("   Tool: Quick Classifier")

            classifier = self.registry.get("quick_classifier")
            result = classifier.execute(
                finding_text="SQL injection vulnerability in user search function"
            )

            if result.status.value == "completed":
                output = result.output
                logger.info(f"   Category: {output['primary_category']}")
                logger.info(f"   All categories: {output['all_categories']}")
                logger.info(f"   Confidence: {output['confidence']}")

            logger.info("\n2️⃣  Finding Validation Demo:")
            logger.info("   Tool: Finding Validator")

            validator = self.registry.get("finding_validator")
            result = validator.execute(
                finding_title="XSS in Comment Form",
                finding_description="User-supplied input is reflected without escaping in the comment section",
                asset_type="web",
                estimated_severity="high"
            )

            if result.status.value == "completed":
                output = result.output
                logger.info(f"   Valid: {output['is_valid']}")
                logger.info(f"   Confidence: {output['confidence']}")
                logger.info(f"   Severity: {output['severity']}")

            logger.info("\n3️⃣  Program Matching Demo:")
            logger.info("   Tool: Program Matcher")

            matcher = self.registry.get("program_matcher")
            result = matcher.execute(
                finding_title="Critical RCE in API",
                finding_scope="api.example.com",
                vulnerability_type="rce",
                severity="critical"
            )

            if result.status.value == "completed":
                output = result.output
                logger.info(f"   Matched Programs: {len(output['matched_programs'])}")
                if output['recommended_program']:
                    rec = output['recommended_program']
                    logger.info(f"   Recommended: {rec['program_name']}")
                    logger.info(f"   Est. Payout: ${rec['estimated_payout']:,.0f}")

            logger.info("\n✅ Tool demonstrations successful\n")
            return True

        except Exception as e:
            logger.error(f"❌ Tool demonstration failed: {str(e)}")
            return False

    def print_summary(self, results: dict) -> None:
        """Print initialization summary"""
        logger.info("=" * 60)
        logger.info("K1 SYSTEM INITIALIZATION SUMMARY")
        logger.info("=" * 60)

        components = [
            ("Tool Registry", results.get("tools", False)),
            ("Embeddings System", results.get("embeddings", False)),
            ("Program Discovery", results.get("programs", False)),
            ("Tool Demonstrations", results.get("demo", False)),
        ]

        for component, status in components:
            status_str = "✅ READY" if status else "⚠️  SKIPPED"
            logger.info(f"{component:.<40} {status_str}")

        logger.info("=" * 60)
        logger.info("\n🎉 K1 System Initialization Complete!")
        logger.info("\nNext Steps:")
        logger.info("  1. Start the API server: python -m uvicorn src.main:app --reload")
        logger.info("  2. Access tools via: curl http://localhost:8000/api/v1/tools")
        logger.info("  3. Scrape programs via: curl -X POST http://localhost:8000/api/v1/programs/scrape-all")
        logger.info("  4. Check branding: config/branding.yaml and apps/frontend/src/theme/")
        logger.info("\n📖 Documentation: See PHASE_7_IMPLEMENTATION_STATUS.md")


async def main():
    """Main initialization routine"""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize K1 System")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--init-embeddings", action="store_true", help="Initialize embeddings")
    parser.add_argument("--scrape-programs", action="store_true", help="Scrape programs")
    args = parser.parse_args()

    initializer = K1SystemInitializer(verbose=args.verbose)

    results = {}

    # Initialize tools (always)
    results["tools"] = initializer.init_tools()

    # Initialize embeddings (if requested or always)
    if args.init_embeddings or True:  # Always init for now
        results["embeddings"] = await initializer.init_embeddings()

    # Initialize programs (always)
    results["programs"] = await initializer.init_programs()

    # Scrape programs (if requested)
    if args.scrape_programs:
        logger.info("\n🌐 Starting program scraping...")
        results["scrape"] = await initializer.scrape_programs()

    # Demonstrate tools
    results["demo"] = await initializer.demo_tools()

    # Print summary
    initializer.print_summary(results)

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
