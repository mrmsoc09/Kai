# Synthetic Data for Kai Platform

This directory contains synthetic (generated) data to support testing, training, and validation of the Kai bug bounty orchestration platform. All data is marked as synthetic and should not be used for real scans.

## Directory Structure

- `targets/`: Mock target definitions (domains, IPs, etc.)
- `artifacts/`: Simulated scan artifacts (DNS records, services, web apps, URLs)
- `observations/`: Generated observations and findings
- `training/`: AI training datasets (prompt-response pairs)
- `advanced/`: Advanced synthetic data (vulnerability chains, zero-days)

## Usage

- Load these files in dry-run mode for workflow testing.
- Use training data to fine-tune AI agents.
- Extend generators to create more diverse data.

## Advanced Features

- **Vulnerability Chains**: Pre-defined exploit chains (web app, API, network) with success probabilities.
- **Zero-Day Scenarios**: Simulated unknown vulnerabilities with detection indicators.
- **Customizable Generation**: Modify `scripts/generate_advanced_synthetic_data.py` for custom chains/scenarios.

## Integration

- Use `SyntheticDataLoader` in `apps/backend/src/core/synthetic_data_loader.py` to load into database.
- Run `scripts/generate_advanced_synthetic_data.py` to generate new advanced data.

## Autonomous Operation

The platform supports fully autonomous training data management:

### Scheduled Tasks (via Celery Beat)
- **Daily Real Data Updates**: Automatically chunks real scan data at 6 AM daily
- **Weekly Synthetic Generation**: Generates new advanced synthetic data every Sunday at 6 AM

### On-Demand Operations
- **CLI**: `kai-cli training update-real-training-data`, `kai-cli training generate-advanced-synthetic`
- **API**: POST `/training/update-real-data`, POST `/training/generate-synthetic`
- **Task Status**: GET `/training/status/{task_id}`

### Setup
Run `scripts/setup_autonomous_training.sh` to configure autonomous operation.

### Monitoring
- Check `logs/daily_training_update.log` for update status
- Monitor Celery tasks via Flower or CLI
- API endpoints provide task status and results

## Notes

- All IDs prefixed with 'syn-' for easy identification.
- Data aligns with schemas in `apps/backend/src/schemas/bugbounty.py`.
- Flagged as `synthetic: true` in metadata where applicable.