from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class JobState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELED = "CANCELED"


@dataclass
class ExecutionJob:
    job_id: str
    campaign_id: str
    tool_name: str
    target: str
    state: JobState
    attempt: int = 1
    max_attempts: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


class ExecutionStateStore:
    """Simple dict-backed in-memory store.

    Replace with Redis or DB-backed store for production.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ExecutionJob] = {}

    def save(self, job: ExecutionJob) -> None:
        job.updated_at = datetime.now(timezone.utc)
        self._jobs[job.job_id] = job

    def load(self, job_id: str) -> ExecutionJob | None:
        return self._jobs.get(job_id)

    def list_by_campaign(self, campaign_id: str) -> list[ExecutionJob]:
        return [j for j in self._jobs.values() if j.campaign_id == campaign_id]

    def all_jobs(self) -> list[ExecutionJob]:
        return list(self._jobs.values())


class ExecutionOrchestrator:
    """In-memory job orchestrator with retry support."""

    def __init__(self, store: ExecutionStateStore | None = None) -> None:
        self.store = store or ExecutionStateStore()

    def submit_job(
        self,
        campaign_id: str,
        tool_name: str,
        target: str,
        max_attempts: int = 3,
    ) -> ExecutionJob:
        job = ExecutionJob(
            job_id=str(uuid.uuid4()),
            campaign_id=campaign_id,
            tool_name=tool_name,
            target=target,
            state=JobState.PENDING,
            max_attempts=max_attempts,
        )
        self.store.save(job)
        return job

    def mark_running(self, job_id: str) -> ExecutionJob:
        job = self.store.load(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.state = JobState.RUNNING
        self.store.save(job)
        return job

    def mark_completed(self, job_id: str) -> ExecutionJob:
        job = self.store.load(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.state = JobState.COMPLETED
        job.error = None
        self.store.save(job)
        return job

    def mark_failed(self, job_id: str, error: str) -> ExecutionJob:
        job = self.store.load(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.error = error
        if job.attempt < job.max_attempts:
            job.state = JobState.RETRYING
            job.attempt += 1
        else:
            job.state = JobState.FAILED
        self.store.save(job)
        return job

    def cancel_job(self, job_id: str) -> ExecutionJob:
        job = self.store.load(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")
        job.state = JobState.CANCELED
        self.store.save(job)
        return job

    def get_retryable_jobs(self) -> list[ExecutionJob]:
        return [j for j in self.store.all_jobs() if j.state == JobState.RETRYING]

    def get_campaign_state(self, campaign_id: str) -> dict[str, int]:
        jobs = self.store.list_by_campaign(campaign_id)
        counts = {
            "total": len(jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "retrying": 0,
        }
        for job in jobs:
            key = job.state.value.lower()
            if key in counts:
                counts[key] += 1
        return counts
