"""
Playwright-based Headless Recording Client.
Captures web-based exploitation sequences with browser automation.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class PlaywrightConfig:
    """Playwright browser configuration."""

    headless: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    width: int = 1920
    height: int = 1080
    device_scale_factor: float = 1.0
    locale: str = "en-US"
    timezone_id: str = "America/New_York"
    viewport_width: int = 1920
    viewport_height: int = 1080


class RecordingClient:
    """
    Headless Playwright client for recording exploitation sequences.
    Captures browser interactions and saves as WebM video.
    """

    def __init__(self, config: PlaywrightConfig | None = None):
        """Initialize recording client."""
        self.config = config or PlaywrightConfig()
        self.browser = None
        self.context = None
        self.page = None
        self.interaction_log: list[Dict[str, Any]] = []

        logger.info(
            f"RecordingClient initialized (browser={self.config.browser_type}, "
            f"headless={self.config.headless})"
        )

    async def initialize(self) -> bool:
        """
        Initialize Playwright browser and context.

        Returns:
            True if successful, False otherwise
        """
        try:
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()

            # Launch browser
            if self.config.browser_type == "chromium":
                self.browser = await playwright.chromium.launch(
                    headless=self.config.headless
                )
            elif self.config.browser_type == "firefox":
                self.browser = await playwright.firefox.launch(
                    headless=self.config.headless
                )
            elif self.config.browser_type == "webkit":
                self.browser = await playwright.webkit.launch(
                    headless=self.config.headless
                )
            else:
                logger.error(f"Unknown browser type: {self.config.browser_type}")
                return False

            # Create context with recording enabled
            self.context = await self.browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                device_scale_factor=self.config.device_scale_factor,
                locale=self.config.locale,
                timezone_id=self.config.timezone_id,
            )

            # Create page
            self.page = await self.context.new_page()

            logger.info("Playwright browser and context initialized successfully")
            return True

        except ImportError:
            logger.error(
                "Playwright not installed. Run: pip install playwright && playwright install"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}")
            return False

    async def start_recording(
        self, output_path: str | Path
    ) -> bool:
        """
        Start video recording.

        Args:
            output_path: Path to save WebM video

        Returns:
            True if recording started successfully
        """
        if not self.page:
            logger.error("Page not initialized")
            return False

        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Start recording
            await self.page.start_trace(path=output_path.with_suffix(".trace"))

            logger.info(f"Recording started: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {str(e)}")
            return False

    async def navigate(
        self,
        url: str,
        wait_until: str = "networkidle",
        timeout_ms: int = 30000,
    ) -> bool:
        """
        Navigate to URL.

        Args:
            url: Target URL
            wait_until: networkidle, load, domcontentloaded
            timeout_ms: Timeout in milliseconds

        Returns:
            True if navigation successful
        """
        if not self.page:
            logger.error("Page not initialized")
            return False

        try:
            await self.page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            self._log_interaction("navigate", {"url": url})
            logger.info(f"Navigated to {url}")
            return True

        except Exception as e:
            logger.error(f"Navigation failed: {str(e)}")
            self._log_interaction("navigate_failed", {"url": url, "error": str(e)})
            return False

    async def click_element(self, selector: str, delay_ms: int = 0) -> bool:
        """Click DOM element."""
        if not self.page:
            return False

        try:
            await self.page.click(selector)
            await asyncio.sleep(delay_ms / 1000)
            self._log_interaction("click", {"selector": selector})
            return True
        except Exception as e:
            logger.error(f"Click failed: {str(e)}")
            self._log_interaction("click_failed", {"selector": selector, "error": str(e)})
            return False

    async def fill_input(self, selector: str, text: str) -> bool:
        """Fill input field."""
        if not self.page:
            return False

        try:
            await self.page.fill(selector, text)
            self._log_interaction("fill_input", {"selector": selector, "text_length": len(text)})
            return True
        except Exception as e:
            logger.error(f"Fill input failed: {str(e)}")
            return False

    async def type_text(self, selector: str, text: str, delay_ms: int = 50) -> bool:
        """Type text with human-like delays."""
        if not self.page:
            return False

        try:
            await self.page.type(selector, text, delay=delay_ms)
            self._log_interaction("type_text", {"selector": selector, "length": len(text)})
            return True
        except Exception as e:
            logger.error(f"Type text failed: {str(e)}")
            return False

    async def wait_for_selector(
        self,
        selector: str,
        timeout_ms: int = 5000,
        state: str = "visible",
    ) -> bool:
        """Wait for element to appear."""
        if not self.page:
            return False

        try:
            await self.page.wait_for_selector(selector, timeout=timeout_ms, state=state)
            self._log_interaction("wait_for_selector", {"selector": selector, "state": state})
            return True
        except Exception as e:
            logger.warning(f"Wait for selector timeout: {str(e)}")
            return False

    async def wait_for_navigation(self, timeout_ms: int = 30000) -> bool:
        """Wait for navigation to complete."""
        if not self.page:
            return False

        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
            self._log_interaction("wait_for_navigation", {})
            return True
        except Exception as e:
            logger.warning(f"Wait for navigation timeout: {str(e)}")
            return False

    async def take_screenshot(self, output_path: str | Path) -> bool:
        """Take screenshot of current page."""
        if not self.page:
            return False

        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            await self.page.screenshot(path=output_path, full_page=True)
            self._log_interaction("screenshot", {"path": str(output_path)})
            return True
        except Exception as e:
            logger.error(f"Screenshot failed: {str(e)}")
            return False

    async def execute_script(self, script: str) -> Any:
        """Execute JavaScript."""
        if not self.page:
            return None

        try:
            result = await self.page.evaluate(script)
            self._log_interaction("execute_script", {"script_length": len(script)})
            return result
        except Exception as e:
            logger.error(f"Script execution failed: {str(e)}")
            return None

    async def get_page_content(self) -> str | None:
        """Get page HTML content."""
        if not self.page:
            return None

        try:
            content = await self.page.content()
            return content
        except Exception as e:
            logger.error(f"Failed to get page content: {str(e)}")
            return None

    async def get_request_headers(self) -> Dict[str, str]:
        """Get current request headers."""
        if not self.page:
            return {}

        try:
            # This is a simplified version; in reality you'd intercept requests
            headers = {
                "User-Agent": await self.page.evaluate("navigator.userAgent"),
            }
            return headers
        except Exception as e:
            logger.error(f"Failed to get headers: {str(e)}")
            return {}

    async def stop_recording(self, output_path: str | Path) -> bool:
        """
        Stop recording and save trace.

        Args:
            output_path: Path to save trace file

        Returns:
            True if successful
        """
        if not self.page:
            return False

        try:
            output_path = Path(output_path)
            await self.page.stop_trace()

            logger.info(f"Recording stopped: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop recording: {str(e)}")
            return False

    async def close(self) -> None:
        """Close browser and cleanup."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")

    def _log_interaction(self, action: str, details: Dict[str, Any]) -> None:
        """Log browser interaction."""
        self.interaction_log.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "details": details,
            }
        )

    def get_interaction_log(self) -> list[Dict[str, Any]]:
        """Get all recorded interactions."""
        return self.interaction_log.copy()

    def export_interaction_log(self, output_path: str | Path) -> bool:
        """Export interaction log as JSON."""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(
                    {
                        "exported_at": datetime.now(timezone.utc).isoformat(),
                        "interaction_count": len(self.interaction_log),
                        "interactions": self.interaction_log,
                    },
                    f,
                    indent=2,
                )

            logger.info(f"Exported interaction log to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export interaction log: {str(e)}")
            return False


class RecordingSession:
    """Manages a complete recording session."""

    def __init__(
        self,
        task_id: str,
        target_url: str,
        recording_dir: str = "apps/backend/data/vault/evidence/recordings",
        config: PlaywrightConfig | None = None,
    ):
        """Initialize recording session."""
        self.task_id = task_id
        self.target_url = target_url
        self.recording_dir = Path(recording_dir)
        self.recording_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or PlaywrightConfig()
        self.client = RecordingClient(self.config)
        self.start_time = None
        self.end_time = None

    async def start(self) -> bool:
        """Start recording session."""
        self.start_time = datetime.now(timezone.utc)

        if not await self.client.initialize():
            return False

        output_path = (
            self.recording_dir / f"{self.task_id}_recording.webm"
        )

        if not await self.client.start_recording(output_path):
            return False

        logger.info(f"Recording session started for {self.task_id}")
        return True

    async def stop(self) -> Dict[str, Any] | None:
        """Stop recording and collect metadata."""
        self.end_time = datetime.now(timezone.utc)

        if not self.start_time:
            logger.error("Recording not started")
            return None

        duration_seconds = (self.end_time - self.start_time).total_seconds()

        # Save interaction log
        log_path = self.recording_dir / f"{self.task_id}_interactions.json"
        await asyncio.to_thread(self.client.export_interaction_log, log_path)

        # Stop recording
        output_path = (
            self.recording_dir / f"{self.task_id}_recording.webm"
        )
        if not await self.client.stop_recording(output_path):
            return None

        # Save metadata
        metadata = {
            "task_id": self.task_id,
            "target_url": self.target_url,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": duration_seconds,
            "recording_path": str(output_path),
            "interactions_count": len(self.client.interaction_log),
            "config": {
                "headless": self.config.headless,
                "browser_type": self.config.browser_type,
                "width": self.config.width,
                "height": self.config.height,
            },
        }

        metadata_path = output_path.with_suffix(".json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        await self.client.close()

        logger.info(
            f"Recording session stopped for {self.task_id} "
            f"(duration: {duration_seconds:.1f}s)"
        )

        return metadata
