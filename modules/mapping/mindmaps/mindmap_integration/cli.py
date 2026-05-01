"""
Command Line Interface for Mindmap Integration System.
"""

import argparse
import sys
import os
from pathlib import Path

from .core.mapper import MindmapMapper
from .config import Config


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Mindmap Integration System - Automated architectural mapping and brainstorming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Map codebase architecture
  python -m mindmap_integration map-code ./src --output arch.mmd
  
  # Generate attack surface from scan results
  python -m mindmap_integration map-scan results.sarif --output attack_surface.puml
  
  # AI brainstorming session
  python -m mindmap_integration brainstorm "Microservices Architecture" --depth 4
  
  # Convert between formats
  python -m mindmap_integration convert input.mmd output.puml --format plantuml
        """
    )
    
    parser.add_argument('--config', '-c', help='Configuration file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Map codebase command
    map_code_parser = subparsers.add_parser('map-code', help='Generate mindmap from codebase')
    map_code_parser.add_argument('source', help='Path to codebase directory or file')
    map_code_parser.add_argument('--output', '-o', help='Output file path')
    map_code_parser.add_argument('--format', '-f', choices=['mermaid', 'plantuml', 'markdown'], 
                                default='mermaid', help='Output format')
    map_code_parser.add_argument('--no-ai', action='store_true', 
                                help='Disable AI enhancement')
    
    # Map scan command
    map_scan_parser = subparsers.add_parser('map-scan', help='Generate attack surface from scan results')
    map_scan_parser.add_argument('scan_file', help='Path to SARIF or JSON scan results')
    map_scan_parser.add_argument('--codebase', help='Path to codebase for context')
    map_scan_parser.add_argument('--output', '-o', required=True, help='Output file path')
    map_scan_parser.add_argument('--format', '-f', choices=['mermaid', 'plantuml'], 
                                default='mermaid', help='Output format')
    
    # Brainstorm command
    brainstorm_parser = subparsers.add_parser('brainstorm', help='AI-driven brainstorming session')
    brainstorm_parser.add_argument('topic', help='Central topic for brainstorming')
    brainstorm_parser.add_argument('--context', help='Additional context or constraints')
    brainstorm_parser.add_argument('--depth', '-d', type=int, default=3, 
                                  help='Expansion depth (1-5)')
    brainstorm_parser.add_argument('--output', '-o', help='Output file path')
    
    # Convert command
    convert_parser = subparsers.add_parser('convert', help='Convert between formats')
    convert_parser.add_argument('input', help='Input file path')
    convert_parser.add_argument('output', help='Output file path')
    convert_parser.add_argument('--format', '-f', choices=['mermaid', 'plantuml', 'markdown'], 
                               required=True, help='Target format')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Load configuration
    config = Config.from_file(args.config) if args.config else Config()
    
    # Initialize mapper
    mapper = MindmapMapper(config.to_dict())
    
    try:
        if args.command == 'map-code':
            mindmap = mapper.map_codebase(
                source_path=args.source,
                output_path=args.output,
                format_type=args.format,
                ai_enhance=not args.no_ai
            )
            if args.verbose:
                print(f"Generated mindmap with {len(mindmap.nodes)} nodes and {len(mindmap.edges)} edges")
            if not args.output:
                # Print to stdout
                from .generators.mermaid_generator import MermaidGenerator
                from .generators.plantuml_generator import PlantUMLGenerator
                
                if args.format == 'mermaid':
                    print(MermaidGenerator().generate(mindmap))
                elif args.format == 'plantuml':
                    print(PlantUMLGenerator().generate(mindmap))
                else:
                    print(mindmap.to_dict())
                    
        elif args.command == 'map-scan':
            mindmap = mapper.map_scan_results(
                scan_path=args.scan_file,
                codebase_path=args.codebase,
                output_path=args.output,
                format_type=args.format
            )
            if args.verbose:
                print(f"Generated attack surface map with {len(mindmap.nodes)} vulnerabilities mapped")
                
        elif args.command == 'brainstorm':
            mindmap = mapper.brainstorm_topic(
                topic=args.topic,
                context=args.context,
                depth=args.depth,
                output_path=args.output
            )
            if args.verbose:
                print(f"Brainstorming complete: {len(mindmap.nodes)} ideas generated")
            if not args.output:
                from .generators.mermaid_generator import MermaidGenerator
                print(MermaidGenerator().generate(mindmap))
                
        elif args.command == 'convert':
            mapper.convert_format(args.input, args.output, args.format)
            if args.verbose:
                print(f"Converted {args.input} to {args.format} format: {args.output}")
                
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
