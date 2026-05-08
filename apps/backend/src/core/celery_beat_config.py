"""Celery Beat configuration for scheduled tasks."""

from celery.schedules import crontab

# Scheduled tasks
beat_schedule = {
    "update-training-data-daily": {
        "task": "training.update_real_training_data",
        "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM
        "args": ("/home/k1-admin/Kai/real_scan_data",),
    },
    "generate-synthetic-data-weekly": {
        "task": "training.generate_synthetic_data",
        "schedule": crontab(day_of_week=0, hour=6, minute=0),  # Weekly on Sunday at 6 AM
        "args": ("/home/k1-admin/Kai/synthetic_data", 10, 5),
    },
}

# Timezone
timezone = "UTC"