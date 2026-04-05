# WhatWeb False Positives

## Header Spoofing
Reverse proxies and security middleboxes can inject or mask headers, leading to incorrect technology inference.

## Theme/Asset Ambiguity
Frontend assets can resemble frameworks that are not actually present server-side.

## Plugin Signature Collisions
Multiple products may share similar response fingerprints.

## Mitigation
Require corroboration from additional probes and prioritize version-confirmed findings.
