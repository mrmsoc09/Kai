#!/bin/bash
# Daily update script for real scan data training chunks (now uses Celery)

cd /home/k1-admin/Kai

# Activate virtual environment
source venv/bin/activate

# Trigger Celery task for training data update
python -c "
from apps.backend.src.core.training_tasks import update_real_training_data_task
result = update_real_training_data_task.delay()
print(f'Training update task queued: {result.id}')
"

echo "Real scan data training chunks update task queued at $(date)" >> /home/k1-admin/Kai/logs/daily_training_update.log