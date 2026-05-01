# Advanced Scripting Orchestrator

A comprehensive Python system for managing, generating, and executing complex security and automation scripts.

## Features

1. **Script Repository**: Metadata management with tagging and versioning
2. **Execution Environment**: Sandboxed execution with resource monitoring (CPU, memory, time)
3. **Task Dependencies**: DAG-based dependency management with topological ordering
4. **AI Integration**: Autonomous script generation using Kimi k2.5
5. **Multi-Language Support**: Python, Bash, and Go handlers with language-specific optimizations

## Architecture

The system uses a modular architecture:

- **Repository Layer**: SQLAlchemy-based storage with many-to-many tagging
- **Execution Engine**: Subprocess-based sandboxing with psutil monitoring
- **Scheduler**: DAG validation and cron-based scheduling
- **AI Generator**: Integration with Kimi k2.5 for secure code generation
- **API/CLI**: FastAPI REST interface and Click-based CLI

## Quick Start

1. Install dependencies:
