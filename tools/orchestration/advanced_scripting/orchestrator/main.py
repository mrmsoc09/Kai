"""
Entry point for the Advanced Scripting Orchestrator.
"""
import sys
import argparse
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.api import app
from orchestrator.cli import main as cli_main
from orchestrator.models import init_database
from orchestrator.config import config


def run_api(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the REST API server."""
    import uvicorn
    print(f"Starting Advanced Scripting Orchestrator API on {host}:{port}")
    uvicorn.run(app, host=host, port=port, reload=reload)


def init_system():
    """Initialize the database and system."""
    print("Initializing Advanced Scripting Orchestrator...")
    engine = init_database(config.db.url)
    print(f"Database initialized at {config.db.url}")
    print("System ready.")


def main():
    parser = argparse.ArgumentParser(description="Advanced Scripting Orchestrator")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # API command
    api_parser = subparsers.add_parser('api', help='Run REST API server')
    api_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    api_parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    api_parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    # Init command
    subparsers.add_parser('init', help='Initialize database')
    
    # CLI command (pass through to click CLI)
    cli_parser = subparsers.add_parser('cli', help='Run CLI commands')
    cli_parser.add_argument('args', nargs=argparse.REMAINDER, help='CLI arguments')
    
    args = parser.parse_args()
    
    if args.command == 'api':
        run_api(args.host, args.port, args.reload)
    elif args.command == 'init':
        init_system()
    elif args.command == 'cli':
        # Pass remaining args to CLI
        sys.argv = [sys.argv[0]] + args.args
        cli_main()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
