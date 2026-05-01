# Nuclei Template Generator

Autonomous generation of Nuclei vulnerability scanning templates using AI-assisted architectural patterns.

## Architecture Overview

This tool follows a **Pipeline Architecture** with **Strategy Pattern** for input parsing:

1. **Input Layer**: Supports CVE IDs, HTTP request/response pairs, and natural language descriptions
2. **Analysis Layer**: Pattern matching using CVE classifiers and vulnerability indicators
3. **Template Engine**: Jinja2-based YAML generation with strict validation
4. **Output Layer**: Validated Nuclei YAML templates

## Installation

