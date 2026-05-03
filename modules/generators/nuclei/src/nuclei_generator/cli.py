"""
Command Line Interface for Nuclei Template Generator.
Provides unified interface for all generation modes.
"""

import os
import sys
import yaml
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path

from .generator import TemplateGenerator
from .parsers.cve_parser import CVEParser
from .parsers.http_parser import HTTPParser
from .patterns.common_patterns import PatternLibrary


console = Console()


@click.group()
@click.version_option(version="1.0.0")
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.pass_context
def cli(ctx, config):
    """Nuclei Template Generator - Autonomous security template creation."""
    ctx.ensure_object(dict)
    
    # Load config
    config_data = {}
    if config:
        with open(config) as f:
            config_data = yaml.safe_load(f)
    elif os.path.exists("config.yaml"):
        with open("config.yaml") as f:
            config_data = yaml.safe_load(f)
    
    ctx.obj['config'] = config_data
    ctx.obj['generator'] = TemplateGenerator()


@cli.command()
@click.argument('cve_id')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--api-key', envvar='NVD_API_KEY', help='NVD API Key')
@click.pass_context
def from_cve(ctx, cve_id, output, api_key):
    """Generate template from CVE ID (e.g., CVE-2021-44228)."""
    config = ctx.obj['config']
    generator = ctx.obj['generator']
    
    # Setup CVE parser
    rate_limit = config.get('cve', {}).get('rate_limit', 6)
    parser = CVEParser(api_key=api_key, rate_limit=rate_limit)
    
    with console.status(f"[bold green]Fetching {cve_id}..."):
        cve_data = parser.fetch(cve_id)
    
    if not cve_data:
        console.print(f"[red]Failed to fetch CVE data for {cve_id}[/red]")
        sys.exit(1)
    
    # Generate output path if not provided
    if not output:
        output_dir = config.get('output', {}).get('directory', './generated_templates')
        os.makedirs(output_dir, exist_ok=True)
        output = os.path.join(output_dir, f"{cve_id.lower()}.yaml")
    
    try:
        with console.status("[bold green]Generating template..."):
            result = generator.generate_from_cve(cve_data, output)
        
        console.print(f"[green]✓[/green] Template generated: {output}")
        
        # Display preview
        console.print("\n[bold]Preview:[/bold]")
        console.print(result[:500] + "..." if len(result) > 500 else result)
        
    except Exception as e:
        console.print(f"[red]Error generating template: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('request_file', type=click.File('r'))
@click.option('--response', '-r', type=click.File('r'), help='Response file (optional)')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--pattern', '-p', multiple=True, help='Pattern to apply (can be used multiple times)')
@click.pass_context
def from_http(ctx, request_file, response, output, pattern):
    """Generate template from HTTP request/response files."""
    generator = ctx.obj['generator']
    
    # Read files
    req_content = request_file.read()
    resp_content = response.read() if response else ""
    
    # Parse HTTP
    parser = HTTPParser()
    
    try:
        interaction = parser.parse_raw(req_content, resp_content)
    except Exception as e:
        console.print(f"[red]Error parsing HTTP: {e}[/red]")
        sys.exit(1)
    
    # Generate output path
    if not output:
        config = ctx.obj['config']
        output_dir = config.get('output', {}).get('directory', './generated_templates')
        os.makedirs(output_dir, exist_ok=True)
        safe_name = Path(request_file.name).stem
        output = os.path.join(output_dir, f"{safe_name}.yaml")
    
    try:
        patterns = list(pattern) if pattern else None
        result = generator.generate_from_http(interaction, patterns, output)
        
        console.print(f"[green]✓[/green] Template generated: {output}")
        
        # Show detected indicators
        indicators = interaction.detect_vulnerability_indicators(interaction)
        if indicators:
            console.print(f"[yellow]Detected indicators:[/yellow] {', '.join(indicators)}")
            
    except Exception as e:
        console.print(f"[red]Error generating template: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument('description')
@click.option('--name', '-n', required=True, help='Vulnerability name')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.pass_context
def from_desc(ctx, description, name, output):
    """Generate template from vulnerability description text."""
    generator = ctx.obj['generator']
    
    if not output:
        config = ctx.obj['config']
        output_dir = config.get('output', {}).get('directory', './generated_templates')
        os.makedirs(output_dir, exist_ok=True)
        safe_name = name.lower().replace(' ', '-').replace('/', '-')[:30]
        output = os.path.join(output_dir, f"{safe_name}.yaml")
    
    try:
        result = generator.generate_from_description(description, name, output)
        console.print(f"[green]✓[/green] Template generated: {output}")
    except Exception as e:
        console.print(f"[red]Error generating template: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.pass_context
def from_interactive(ctx, output):
    """Interactive mode for template generation."""
    console.print("[bold]Nuclei Template Generator - Interactive Mode[/bold]\n")
    
    # Select input type
    input_type = click.Choice(['cve', 'http', 'description'])
    choice = click.prompt("Select input type", type=input_type)
    
    generator = ctx.obj['generator']
    
    if choice == 'cve':
        cve_id = click.prompt("Enter CVE ID")
        ctx.invoke(from_cve, cve_id=cve_id, output=output, api_key=None)
        
    elif choice == 'http':
        req_file = click.prompt("Request file path", type=click.Path(exists=True))
        resp_file = click.prompt("Response file path (optional)", type=click.Path(), default="")
        
        with open(req_file, 'r') as f:
            req_content = f.read()
        
        resp_content = ""
        if resp_file and os.path.exists(resp_file):
            with open(resp_file, 'r') as f:
                resp_content = f.read()
        
        parser = HTTPParser()
        interaction = parser.parse_raw(req_content, resp_content)
        
        # Show available patterns
        library = PatternLibrary()
        table = Table(title="Available Patterns")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Tags", style="yellow")
        
        for name in library.list_patterns():
            pattern = library.get(name)
            table.add_row(name, pattern.description, ", ".join(pattern.tags[:3]))
        
        console.print(table)
        
        patterns = click.prompt("Enter patterns to apply (comma-separated, or 'auto')", 
                               default="auto")
        pattern_list = None if patterns == "auto" else [p.strip() for p in patterns.split(",")]
        
        if not output:
            output = f"generated_{Path(req_file).stem}.yaml"
            
        result = generator.generate_from_http(interaction, pattern_list, output)
        console.print(f"[green]Generated:[/green] {output}")
        
    elif choice == 'description':
        name = click.prompt("Vulnerability name")
        description = click.prompt("Description", prompt_suffix=": ")
        ctx.invoke(from_desc, description=description, name=name, output=output)


@cli.command()
def list_patterns():
    """List available vulnerability patterns."""
    library = PatternLibrary()
    
    table = Table(title="Available Vulnerability Patterns")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="green")
    table.add_column("Severity", style="red")
    table.add_column("Tags", style="yellow")
    
    for name in library.list_patterns():
        pattern = library.get(name)
        table.add_row(
            name,
            pattern.description[:50] + "..." if len(pattern.description) > 50 else pattern.description,
            pattern.severity,
            ", ".join(pattern.tags[:2])
        )
    
    console.print(table)


def main():
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
