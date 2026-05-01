"""
Command Line Interface for the Content Generation Engine.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from content_engine.config import settings
from content_engine.generators import (
    IntelligenceReportGenerator,
    ContractingGenerator,
    ThreatIntelGenerator,
    EbookGenerator,
    GuideGenerator
)
from content_engine.models import (
    IntelligenceReport,
    ContractingOpportunity,
    ThreatIntelReport,
    Ebook,
    Guide
)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Content Generation Engine (CGE) - Generate intelligence reports, contracting docs, and more."""
    settings.ensure_directories()


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.option('--format', '-f', type=click.Choice(['markdown', 'html', 'json']), default='markdown')
def intel(input_file, output, format):
    """Generate an intelligence report from JSON/YAML input."""
    data = _load_input(input_file)
    report = IntelligenceReport(**data)
    generator = IntelligenceReportGenerator(output_dir=settings.output_dir)
    
    if output:
        result = generator.generate(report, output_file=output)
        click.echo(f"Generated: {result}")
    else:
        result = generator.generate(report)
        click.echo(result)


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.option('--type', '-t', type=click.Choice(['rfp', 'rfq', 'capabilities']), default='rfp')
def contract(input_file, output, type):
    """Generate contracting documents."""
    data = _load_input(input_file)
    opportunity = ContractingOpportunity(**data)
    generator = ContractingGenerator(output_dir=settings.output_dir)
    
    if output:
        result = generator.generate(opportunity, output_file=output)
        click.echo(f"Generated: {result}")
    else:
        result = generator.generate(opportunity)
        click.echo(result)


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.option('--export-iocs', is_flag=True, help='Export IOCs to separate file')
@click.option('--stix', is_flag=True, help='Generate STIX bundle')
def threat(input_file, output, export_iocs, stix):
    """Generate threat intelligence reports."""
    data = _load_input(input_file)
    report = ThreatIntelReport(**data)
    generator = ThreatIntelGenerator(output_dir=settings.output_dir)
    
    if output:
        result = generator.generate(report, output_file=output)
        click.echo(f"Generated: {result}")
    else:
        result = generator.generate(report)
        click.echo(result)
    
    if export_iocs:
        ioc_file = settings.output_dir / f"{Path(input_file).stem}_iocs.csv"
        iocs = generator.export_iocs(report, format="csv")
        with open(ioc_file, 'w') as f:
            f.write(iocs)
        click.echo(f"Exported IOCs: {ioc_file}")
    
    if stix:
        stix_data = generator.generate_stix_bundle(report)
        stix_file = settings.output_dir / f"{Path(input_file).stem}_stix.json"
        with open(stix_file, 'w') as f:
            json.dump(stix_data, f, indent=2)
        click.echo(f"Exported STIX: {stix_file}")


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.option('--chapter', '-c', type=int, help='Generate specific chapter only')
def ebook(input_file, output, chapter):
    """Generate e-books."""
    data = _load_input(input_file)
    book = Ebook(**data)
    generator = EbookGenerator(output_dir=settings.output_dir)
    
    if chapter:
        result = generator.generate_chapter(book, chapter, output_file=output)
    else:
        result = generator.generate(book, output_file=output)
    
    if isinstance(result, Path):
        click.echo(f"Generated: {result}")
    else:
        click.echo(result)


@main.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.option('--playbook', is_flag=True, help='Treat as operational playbook')
@click.option('--tutorial', is_flag=True, help='Treat as tutorial')
def guide(input_file, output, playbook, tutorial):
    """Generate guides, tutorials, and playbooks."""
    data = _load_input(input_file)
    
    if playbook:
        from content_engine.models.guide import Playbook
        guide_obj = Playbook(**data)
    elif tutorial:
        from content_engine.models.guide import Tutorial
        guide_obj = Tutorial(**data)
    else:
        guide_obj = Guide(**data)
    
    generator = GuideGenerator(output_dir=settings.output_dir)
    
    if output:
        result = generator.generate(guide_obj, output_file=output)
        click.echo(f"Generated: {result}")
    else:
        result = generator.generate(guide_obj)
        click.echo(result)


def _load_input(filepath: str) -> dict:
    """Load input data from JSON or YAML file."""
    path = Path(filepath)
    with open(path, 'r', encoding='utf-8') as f:
        if path.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        elif path.suffix == '.json':
            return json.load(f)
        else:
            # Try to parse as JSON first, then YAML
            content = f.read()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return yaml.safe_load(content)


if __name__ == '__main__':
    main()
