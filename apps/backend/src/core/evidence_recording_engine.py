"""
Automated screen recording engine for exploitation sequences.
Uses Playwright for headless browser recording with artifact management.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    """Configuration for screen recording."""

    task_id: str
    target_url: str
    recording_dir: str = "vault/evidence/videos"
    video_format: str = "mp4"  # or "webm"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    max_duration_seconds: int = 300  # 5 minutes
    capture_audio: bool = False


@dataclass
class RecordingSession:
    """Active recording session."""

    task_id: str
    session_id: str
    target_url: str
    start_time: str
    recording_path: Optional[str] = None
    status: str = "recording"  # recording, stopped, failed
    frames_captured: int = 0
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "target_url": self.target_url,
            "start_time": self.start_time,
            "recording_path": self.recording_path,
            "status": self.status,
            "frames_captured": self.frames_captured,
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "error_message": self.error_message,
        }


class RecordingEngine:
    """
    Automated screen recording engine for exploitation sequences.
    Records browser interactions and saves as video artifacts.
    """

    def __init__(self, config: RecordingConfig):
        """
        Initialize recording engine.

        Args:
            config: RecordingConfig object
        """
        self.config = config
        self.recording_dir = Path(config.recording_dir)
        self.recording_dir.mkdir(parents=True, exist_ok=True)

        # Active sessions
        self.active_sessions: Dict[str, RecordingSession] = {}

        # Recording metadata
        self.recordings_manifest: Dict[str, RecordingSession] = {}

        logger.info(
            f"RecordingEngine initialized for {config.task_id} "
            f"(target: {config.target_url})"
        )

    async def start_recording(
        self, task_id: str, target_url: str
    ) -> RecordingSession:
        """
        Start a new recording session.

        Args:
            task_id: Unique task identifier
            target_url: Target URL being exploited

        Returns:
            RecordingSession object
        """
        import uuid

        session_id = str(uuid.uuid4())[:8]
        start_time = datetime.now(timezone.utc).isoformat()

        session = RecordingSession(
            task_id=task_id,
            session_id=session_id,
            target_url=target_url,
            start_time=start_time,
        )

        self.active_sessions[session_id] = session

        logger.info(
            f"Recording started: {session_id} for task {task_id}"
        )

        return session

    async def record_browser_interaction(
        self,
        session_id: str,
        interaction_type: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Record a single browser interaction.

        Args:
            session_id: Recording session ID
            interaction_type: Type of interaction (click, input, navigation)
            details: Interaction details
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Unknown session: {session_id}")
            return

        session = self.active_sessions[session_id]

        # In production, this would trigger Playwright recording
        # For now, we track metadata
        interaction_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": interaction_type,
            "details": details,
        }

        logger.debug(
            f"[{session_id}] {interaction_type}: {details}"
        )

    async def stop_recording(
        self, session_id: str
    ) -> Optional[RecordingSession]:
        """
        Stop recording and save video artifact.

        Args:
            session_id: Recording session ID

        Returns:
            Completed RecordingSession or None if not found
        """
        if session_id not in self.active_sessions:
            logger.error(f"Unknown session: {session_id}")
            return None

        session = self.active_sessions[session_id]

        try:
            # Calculate duration
            start_time = datetime.fromisoformat(session.start_time)
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Generate video path
            video_filename = (
                f"{session.task_id}_{session.session_id}."
                f"{self.config.video_format}"
            )
            video_path = self.recording_dir / video_filename

            # In production: use Playwright to save recording
            # For PoC: create placeholder with metadata
            await self._create_recording_artifact(
                video_path, session, duration
            )

            session.recording_path = str(video_path)
            session.duration_seconds = duration
            session.status = "stopped"
            session.file_size_bytes = video_path.stat().st_size

            # Save to manifest
            self.recordings_manifest[session_id] = session

            logger.info(
                f"Recording stopped: {session_id} "
                f"({duration:.1f}s, {session.file_size_bytes} bytes)"
            )

            return session

        except Exception as e:
            logger.error(f"Error stopping recording: {str(e)}")
            session.status = "failed"
            session.error_message = str(e)
            return session

        finally:
            # Remove from active sessions
            del self.active_sessions[session_id]

    async def _create_recording_artifact(
        self, video_path: Path, session: RecordingSession, duration: float
    ) -> None:
        """Create recording artifact (placeholder for PoC)."""
        # In production, this writes actual video data
        # For PoC, we create metadata JSON and dummy video
        metadata = {
            "task_id": session.task_id,
            "session_id": session.session_id,
            "target_url": session.target_url,
            "duration_seconds": duration,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "format": self.config.video_format,
            "width": self.config.width,
            "height": self.config.height,
            "fps": self.config.fps,
        }

        # Write metadata
        metadata_path = video_path.with_suffix(".json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Create dummy video file (1 KB placeholder)
        video_path.write_bytes(
            b"MOCK_VIDEO_CONTENT_" + str(duration).encode() * 100
        )

    async def get_recording(
        self, task_id: str
    ) -> Optional[RecordingSession]:
        """Get recording for task."""
        for session in self.recordings_manifest.values():
            if session.task_id == task_id:
                return session
        return None

    async def list_recordings(
        self, task_id: Optional[str] = None
    ) -> list[RecordingSession]:
        """List all recordings, optionally filtered by task."""
        recordings = list(self.recordings_manifest.values())

        if task_id:
            recordings = [r for r in recordings if r.task_id == task_id]

        return sorted(
            recordings, key=lambda r: r.start_time, reverse=True
        )

    def get_recording_stats(self) -> Dict[str, Any]:
        """Get recording statistics."""
        recordings = list(self.recordings_manifest.values())
        total_duration = sum(r.duration_seconds for r in recordings)
        total_size = sum(r.file_size_bytes for r in recordings)

        successful = sum(
            1 for r in recordings if r.status == "stopped"
        )
        failed = sum(1 for r in recordings if r.status == "failed")

        return {
            "total_recordings": len(recordings),
            "successful": successful,
            "failed": failed,
            "total_duration_seconds": total_duration,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "average_duration_seconds": (
                total_duration / len(recordings)
                if recordings
                else 0
            ),
        }

    async def cleanup_old_recordings(
        self, days_old: int = 7
    ) -> int:
        """
        Delete recordings older than specified days.

        Args:
            days_old: Age threshold in days

        Returns:
            Number of recordings deleted
        """
        cutoff = datetime.now(timezone.utc)
        cutoff_seconds = days_old * 86400

        removed = 0
        to_remove = []

        for session_id, session in self.recordings_manifest.items():
            created_time = datetime.fromisoformat(
                session.start_time
            )
            age_seconds = (cutoff - created_time).total_seconds()

            if age_seconds > cutoff_seconds:
                # Delete video file
                if session.recording_path:
                    try:
                        Path(session.recording_path).unlink()
                        # Delete metadata file
                        Path(
                            session.recording_path
                        ).with_suffix(".json").unlink()
                        removed += 1
                        to_remove.append(session_id)
                    except Exception as e:
                        logger.error(f"Error deleting {session.recording_path}: {str(e)}")

        # Remove from manifest
        for session_id in to_remove:
            del self.recordings_manifest[session_id]

        logger.info(f"Cleaned up {removed} old recordings")
        return removed


# Global recording engine instance
_recording_engine: Optional[RecordingEngine] = None


async def get_recording_engine(
    config: Optional[RecordingConfig] = None,
) -> RecordingEngine:
    """Get or create global recording engine."""
    global _recording_engine

    if _recording_engine is None:
        config = config or RecordingConfig(
            task_id="default",
            target_url="http://localhost",
            recording_dir="vault/evidence/videos",
        )
        _recording_engine = RecordingEngine(config)

    return _recording_engine
