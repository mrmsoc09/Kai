# Content Generation Engine (CGE)

A modular Python framework for generating structured content including intelligence reports, US Government contracting documents, threat intelligence reports, e-books, guides, tutorials, and operational playbooks.

## Architecture

The engine uses a layered architecture:

1. **Models Layer**: Pydantic models for data validation and serialization
2. **Generators Layer**: Template-based content generation using Jinja2
3. **Templates Layer**: Modular Jinja2 templates for each content type
4. **Utilities**: Helper functions for formatting and validation

## Installation

