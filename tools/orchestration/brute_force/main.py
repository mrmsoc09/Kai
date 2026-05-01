#!/usr/bin/env python3
"""
BruteFuzz - Main Entry Point
High-performance brute forcing and fuzzing suite
"""

import asyncio
import argparse
import sys
from pathlib import Path

from brutefuzz.core.config import Config
from brutefuzz.core.engine import FuzzingEngine
from brutefuzz.protocols.http import HTTPProtocolHandler
from brutefuzz.protocols.ssh import SSHProtocolHandler
from brutefuzz.wordlists.generator import FileWordlistGenerator, MutationGenerator


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BruteFuzz - Advanced Brute Forcing and Fuzzing Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s http -t example.com -w /path/to/wordlist.txt --path "/admin/{PAYLOAD}"
  %(prog)s ssh -t 192.168.1.1 -u root -w passwords.txt --rate 5
        """
    )
    
    subparsers = parser.add_subparsers(dest="protocol", help="Protocol to use")
    
    # HTTP parser
    http_parser = subparsers.add_parser("http", help="HTTP/HTTPS fuzzing")
    http_parser.add_argument("-t", "--target", required=True, help="Target host")
    http_parser.add_argument("-p", "--port", type=int, help="Target port")
    http_parser.add_argument("--ssl", action="store_true", help="Use HTTPS")
    http_parser.add_argument("-w", "--wordlist", required=True, help="Wordlist file")
    http_parser.add_argument("--path", default="/", help="Target path (use {PAYLOAD} for insertion)")
    http_parser.add_argument("-m", "--method", default="GET", choices=["GET", "POST"])
    http_parser.add_argument("--rate", type=float, default=10.0, help="Requests per second")
    http_parser.add_argument("--workers", type=int, default=50, help="Concurrent workers")
    http_parser.add_argument("--waf-evasion", action="store_true", help="Enable WAF evasion")
    http_parser.add_argument("--ai-mutation", action="store_true", help="Enable AI feedback loop")
    
    # SSH parser
    ssh_parser = subparsers.add_parser("ssh", help="SSH brute force")
    ssh_parser.add_argument("-t", "--target", required=True, help="Target host")
    ssh_parser.add_argument("-p", "--port", type=int, default=22, help="SSH port")
    ssh_parser.add_argument("-u", "--username", required=True, help="Username")
    ssh_parser.add_argument("-w", "--wordlist", required=True, help="Password wordlist")
    ssh_parser.add_argument("--rate", type=float, default=1.0, help="Attempts per second")
    ssh_parser.add_argument("--workers", type=int, default=5, help="Concurrent workers")
    
    # Global options
    parser.add_argument("--config", type=Path, help="Load config from JSON file")
    parser.add_argument("-o", "--output", type=Path, help="Output file for results")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    return parser


async def main():
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.protocol:
        parser.print_help()
        sys.exit(1)
    
    # Load or create config
    if args.config:
        config = Config.from_json(args.config)
    else:
        config = Config()
        
    # Override with CLI args
    if args.verbose:
        config.log_level = "DEBUG"
    if hasattr(args, 'rate'):
        config.requests_per_second = args.rate
    if hasattr(args, 'workers'):
        config.max_workers = args.workers
    if hasattr(args, 'waf_evasion'):
        config.waf_evasion_enabled = args.waf_evasion
    if hasattr(args, 'ai_mutation'):
        config.ai_mutation_enabled = args.ai_mutation
        
    # Setup protocol handler
    if args.protocol == "http":
        handler = HTTPProtocolHandler(
            target=args.target,
            port=args.port,
            use_ssl=args.ssl,
            method=args.method,
            path=args.path
        )
    elif args.protocol == "ssh":
        handler = SSHProtocolHandler(
            target=args.target,
            port=args.port,
            username=args.username
        )
    else:
        print(f"Unknown protocol: {args.protocol}")
        sys.exit(1)
    
    # Setup wordlist generator with mutation
    base_gen = FileWordlistGenerator(Path(args.wordlist))
    generator = MutationGenerator(base_gen, depth=config.mutation_depth)
    
    # Initialize and run engine
    engine = FuzzingEngine(config, handler)
    
    try:
        final_state = await engine.run(generator)
        
        # Report results
        print("\n" + "="*50)
        print("CAMPAIGN COMPLETE")
        print("="*50)
        print(f"Total requests: {final_state.total_requests}")
        print(f"Success rate: {final_state.get_success_rate()*100:.2f}%")
        print(f"Successful payloads: {len(final_state.successful_payloads)}")
        
        if final_state.successful_payloads:
            print("\nSuccessful payloads:")
            for payload in final_state.successful_payloads:
                print(f"  - {payload}")
                
        if args.output:
            with open(args.output, 'w') as f:
                for payload in final_state.successful_payloads:
                    f.write(f"{payload}\n")
            print(f"\nResults saved to {args.output}")
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        await engine.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
