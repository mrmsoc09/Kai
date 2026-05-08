#!/bin/bash
# Start Celery Beat for scheduled tasks

cd /home/k1-admin/Kai

# Activate virtual environment
source venv/bin/activate

# Start Celery Beat
celery -A apps.backend.src.core.celery_app beat --loglevel=info --scheduler celery.beat.PersistentScheduler