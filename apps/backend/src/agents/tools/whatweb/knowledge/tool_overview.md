# WhatWeb

WhatWeb fingerprints web technologies by matching HTTP responses, headers, and signatures against known plugin patterns. It provides stack-level intelligence that improves vulnerability template targeting.

## Primary Purpose
Identify technologies and versions exposed by target web applications.

## Automation Profile
Use low aggression (`--aggression 1`) for safe baseline reconnaissance in autonomous workflows.

## Output
JSON logs support deterministic parsing into structured technology findings.

## Pipeline Role
Feeds nuclei template selection and version-based CVE correlation for searchsploit.
