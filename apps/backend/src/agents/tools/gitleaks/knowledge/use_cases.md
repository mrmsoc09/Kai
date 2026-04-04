# Gitleaks Use Cases

## Scenario 1: CI/CD Integration
Gitleaks as pre-commit hook catches secrets before pushing to remote.

## Scenario 2: Audit of Historical Breaches
Scan full history after security incident. Identifies when secrets were committed.

## Scenario 3: Third-Party Code Assessment
Scan acquired codebase, vendor code, open source dependencies for hardcoded credentials.

## Scenario 4: Regex Pattern Tuning
Create custom gitleaks rules for organization-specific secret formats.

## Scenario 5: Complementary to Trufflehog
Run both tools. Different rulesets catch different secrets. Higher overall recall.
