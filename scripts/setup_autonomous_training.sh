#!/bin/bash
# Setup autonomous training data management for Kai

cd /home/k1-admin/Kai

echo "Setting up autonomous training data management..."

# 1. Set up cron job for daily updates
echo "Setting up daily cron job..."
./scripts/daily_training_update.sh  # This will queue the task

# 2. Start Celery Beat for scheduled tasks
echo "Starting Celery Beat..."
nohup ./scripts/start_celery_beat.sh > logs/celery_beat.log 2>&1 &

echo "Autonomous setup complete!"
echo "Daily updates: Cron job at 6 AM"
echo "Weekly synthetic generation: Celery Beat on Sundays at 6 AM"
echo "On-demand: Use CLI 'kai-cli training update-real-training-data' or API POST /training/update-real-data"
echo "Monitor: Check logs/daily_training_update.log and celery_beat.log"