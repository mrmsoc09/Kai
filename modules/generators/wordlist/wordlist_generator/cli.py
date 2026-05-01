"""Command line interface."""

import asyncio
import argparse
import sys
from pathlib import Path
import logging

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.logging import RichHandler

from wordlist_generator.core.config import WordlistConfig, ScraperConfig, AIConfig, PermutationConfig, FilterConfig
from wordlist_generator.core.engine import WordlistEngine

console = Console()


def setup_logging(verbose: bool):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Custom Wordlist Generator - Context-aware wordlist generation for security testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -t example.com -o wordlist.txt
  %(prog)s -t example.com --ai-expansion --max-depth 3 -o output.txt
  %(prog)s -t example.com --patterns leet,years,special -o wordlist.txt
        """
    )
    
    parser.add_argument(
        "-t", "--target",
        required=True,
        help="Target domain or URL to scrape"
    )
    
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="Output file path"
    )
    
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum crawling depth (default: 2)"
    )
    
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum pages to crawl (default: 50)"
    )
    
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI-driven expansion"
    )
    
    parser.add_argument(
        "--patterns",
        default="original,uppercase,lowercase,capitalize,leet,years",
        help="Comma-separated permutation patterns"
    )
    
    parser.add_argument(
        "--min-length",
        type=int,
        default=4,
        help="Minimum word length"
    )
    
    parser.add_argument(
        "--max-length",
        type=int,
        default=32,
        help="Maximum word length"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers"
    )
    
    return parser


async def main_async():
    """Async main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Build configuration
    config = WordlistConfig(
        target=args.target,
        output_path=args.output,
        scraper=ScraperConfig(
            max_depth=args.max_depth,
            max_pages=args.max_pages
        ),
        ai=AIConfig(
            enabled=not args.no_ai
        ),
        permutation=PermutationConfig(
            patterns=args.patterns.split(','),
            min_length=args.min_length,
            max_length=args.max_length
        ),
        filter=FilterConfig(),
        verbose=args.verbose,
        max_workers=args.workers
    )
    
    console.print(f"[bold blue]Starting wordlist generation for:[/bold blue] {args.target}")
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task(description="Initializing engine...", total=None)
            engine = WordlistEngine(config)
            
            progress.add_task(description="Generating wordlist...", total=None)
            output_path = await engine.generate()
            
        console.print(f"[bold green]Success![/bold green] Wordlist saved to: {output_path}")
        
        # Show stats
        if output_path.exists():
            line_count = sum(1 for _ in open(output_path))
            console.print(f"Total entries: [bold]{line_count}[/bold]")
            
    except KeyboardInterrupt:
        console.print("[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if args.verbose:
            console.print_exception()
        sys.exit(1)


def main():
    """Synchronous entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
