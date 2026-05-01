"""
Command line interface for the Advanced Scripting Orchestrator.
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from sqlalchemy.orm import Session

from .models import init_database, get_session_factory, ScriptLanguage, ScriptStatus
from .repository import ScriptRepository
from .executor import ExecutionEngine
from .ai_generator import ScriptGenerator, GenerationRequest
from .config import config


@click.group()
@click.option('--db', default='sqlite:///orchestrator.db', help='Database URL')
@click.pass_context
def cli(ctx, db):
    """Advanced Scripting Orchestrator CLI"""
    ctx.ensure_object(dict)
    ctx.obj['db_url'] = db
    engine = init_database(db)
    ctx.obj['session_factory'] = get_session_factory(engine)


def get_session(ctx) -> Session:
    return ctx.obj['session_factory']()


@cli.command()
@click.argument('name')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--language', type=click.Choice(['python', 'bash', 'go']), required=True)
@click.option('--description', default='')
@click.option('--author', default='')
@click.option('--tag', multiple=True)
@click.pass_context
def add(ctx, name, file_path, language, description, author, tag):
    """Add a script to the repository"""
    session = get_session(ctx)
    repo = ScriptRepository(session)
    
    content = Path(file_path).read_text()
    
    try:
        script = repo.create_script(
            name=name,
            content=content,
            language=ScriptLanguage(language),
            description=description,
            author=author,
            tags=list(tag)
        )
        click.echo(f"Script added with ID: {script.id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        session.close()


@cli.command()
@click.option('--language', type=click.Choice(['python', 'bash', 'go']))
@click.option('--tag', multiple=True)
@click.pass_context
def list(ctx, language, tag):
    """List scripts in repository"""
    session = get_session(ctx)
    repo = ScriptRepository(session)
    
    scripts = repo.list_scripts(
        language=ScriptLanguage(language) if language else None,
        tags=list(tag) if tag else None
    )
    
    if not scripts:
        click.echo("No scripts found")
        return
    
    click.echo(f"{'ID':<5} {'Name':<30} {'Language':<10} {'Status':<12} {'Tags'}")
    click.echo("-" * 80)
    for s in scripts:
        tags = ", ".join([t.name for t in s.tags])
        click.echo(f"{s.id:<5} {s.name:<30} {s.language.value:<10} {s.status.value:<12} {tags}")


@cli.command()
@click.argument('script_id', type=int)
@click.option('--arg', multiple=True, help='Arguments to pass to script')
@click.option('--env', multiple=True, help='Environment variables (KEY=VALUE)')
@click.pass_context
def run(ctx, script_id, arg, env):
    """Execute a script"""
    session = get_session(ctx)
    repo = ScriptRepository(session)
    
    script = repo.get_script(script_id)
    if not script:
        click.echo(f"Script {script_id} not found", err=True)
        sys.exit(1)
    
    # Parse environment variables
    env_dict = {}
    for e in env:
        if '=' in e:
            k, v = e.split('=', 1)
            env_dict[k] = v
    
    engine = ExecutionEngine()
    
    click.echo(f"Executing script: {script.name}...")
    
    async def execute():
        return await engine.execute_script(
            script=script,
            session=session,
            arguments=list(arg),
            environment=env_dict,
            triggered_by="cli"
        )
    
    execution = asyncio.run(execute())
    
    click.echo(f"\nStatus: {execution.status.value}")
    click.echo(f"Exit code: {execution.exit_code}")
    if execution.output:
        click.echo(f"\nOutput:\n{execution.output}")
    if execution.error_output:
        click.echo(f"\nErrors:\n{execution.error_output}", err=True)


@cli.command()
@click.argument('description')
@click.option('--language', type=click.Choice(['python', 'bash', 'go']), default='python')
@click.option('--requirement', multiple=True)
@click.option('--output', type=click.Path(), help='Save generated script to file')
@click.option('--security', type=click.Choice(['strict', 'standard', 'permissive']), default='strict')
def generate(description, language, requirement, output, security):
    """Generate a script using AI"""
    if not config.ai.api_key:
        click.echo("Error: KIMI_API_KEY not set", err=True)
        sys.exit(1)
    
    gen = ScriptGenerator()
    
    request = GenerationRequest(
        description=description,
        language=ScriptLanguage(language),
        requirements=list(requirement),
        security_level=security
    )
    
    click.echo("Generating script...")
    
    async def do_generate():
        return await gen.generate_script(request)
    
    try:
        code, explanation, metadata = asyncio.run(do_generate())
        
        click.echo(f"\nGenerated Code:\n{'='*60}")
        click.echo(code)
        click.echo(f"{'='*60}\n")
        click.echo(f"Explanation:\n{explanation}\n")
        click.echo(f"Metadata: {json.dumps(metadata, indent=2)}")
        
        if output:
            Path(output).write_text(code)
            click.echo(f"\nSaved to: {output}")
            
    except Exception as e:
        click.echo(f"Generation failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('script_id', type=int)
@click.pass_context
def show(ctx, script_id):
    """Show script details"""
    session = get_session(ctx)
    repo = ScriptRepository(session)
    
    script = repo.get_script(script_id)
    if not script:
        click.echo(f"Script {script_id} not found", err=True)
        sys.exit(1)
    
    click.echo(f"Name: {script.name}")
    click.echo(f"Language: {script.language.value}")
    click.echo(f"Version: {script.version}")
    click.echo(f"Status: {script.status.value}")
    click.echo(f"Author: {script.author}")
    click.echo(f"Tags: {', '.join(t.name for t in script.tags)}")
    click.echo(f"Created: {script.created_at}")
    click.echo(f"Updated: {script.updated_at}")
    click.echo(f"\nDescription:\n{script.description}")
    click.echo(f"\nContent:\n{'='*60}")
    click.echo(script.content)


@cli.command()
@click.argument('script_id', type=int)
@click.pass_context
def history(ctx, script_id):
    """Show execution history for a script"""
    session = get_session(ctx)
    repo = ScriptRepository(session)
    
    executions = repo.get_execution_history(script_id=script_id, limit=20)
    
    if not executions:
        click.echo("No executions found")
        return
    
    click.echo(f"{'ID':<5} {'Status':<12} {'Started':<20} {'Duration'}")
    click.echo("-" * 60)
    
    for e in executions:
        duration = ""
        if e.completed_at and e.started_at:
            delta = e.completed_at - e.started_at
            duration = f"{delta.total_seconds():.2f}s"
        
        started = e.started_at.strftime("%Y-%m-%d %H:%M:%S") if e.started_at else "N/A"
        click.echo(f"{e.id:<5} {e.status.value:<12} {started:<20} {duration}")


def main():
    cli()


if __name__ == '__main__':
    main()
