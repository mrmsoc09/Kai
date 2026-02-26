from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Optional
import logging

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..core.hil_db import dispose_async_engine, get_async_engine

logger = logging.getLogger(__name__)


@dataclass
class Services:
    """Singleton service container managed by FastAPI lifespan."""

    redis: Optional[Redis] = None
    neo4j_available: bool = False
    intelligence_ready: bool = False
    rag_ready: bool = False
    started: bool = False

    def _probe_timeout_seconds(self) -> float:
        raw = os.getenv("HEALTHCHECK_TIMEOUT_SECONDS", "3")
        try:
            return max(0.5, float(raw))
        except ValueError:
            return 3.0

    async def probe_postgres(self) -> dict[str, Any]:
        try:
            engine = get_async_engine()
            timeout = self._probe_timeout_seconds()
            async with asyncio.timeout(timeout):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            return {"ok": True, "status": "up"}
        except SQLAlchemyError as exc:
            return {"ok": False, "status": "down", "error": str(exc)}
        except TimeoutError as exc:
            return {"ok": False, "status": "down", "error": str(exc)}

    async def probe_redis(self) -> dict[str, Any]:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return {"ok": False, "status": "not_configured"}

        client: Redis | None = self.redis
        close_when_done = False
        if client is None:
            client = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            close_when_done = True

        try:
            timeout = self._probe_timeout_seconds()
            async with asyncio.timeout(timeout):
                pong = await client.ping()
            return {"ok": bool(pong), "status": "up" if pong else "down"}
        except TimeoutError as exc:
            return {"ok": False, "status": "down", "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "status": "down", "error": str(exc)}
        finally:
            if close_when_done:
                await client.aclose()

    async def probe_neo4j(self) -> dict[str, Any]:
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_user = os.getenv("NEO4J_USER")
        neo4j_password = os.getenv("NEO4J_PASSWORD")

        if not (neo4j_uri and neo4j_user and neo4j_password):
            return {"ok": False, "status": "not_configured"}

        try:
            from neo4j import AsyncGraphDatabase
            from neo4j.exceptions import AuthError, ServiceUnavailable

            driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            try:
                timeout = self._probe_timeout_seconds()
                async with asyncio.timeout(timeout):
                    await driver.verify_connectivity()
                return {"ok": True, "status": "up"}
            finally:
                await driver.close()
        except (AuthError, ServiceUnavailable, TimeoutError) as exc:
            return {"ok": False, "status": "down", "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "status": "down", "error": str(exc)}

    async def probe_dependencies(self) -> dict[str, dict[str, Any]]:
        postgres = await self.probe_postgres()
        redis = await self.probe_redis()
        neo4j = await self.probe_neo4j()
        return {
            "postgres": postgres,
            "redis": redis,
            "neo4j": neo4j,
        }

    async def startup(self) -> None:
        if self.started:
            return

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            await self.redis.ping()
        except Exception as exc:
            logger.warning("Redis startup skipped: %s", exc)
            self.redis = None

        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_user = os.getenv("NEO4J_USER")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        if neo4j_uri and neo4j_user and neo4j_password:
            try:
                from ..integrations.neo4j_client import (
                    get_neo4j_client,
                    initialize_neo4j,
                )
                await initialize_neo4j(neo4j_uri, neo4j_user, neo4j_password)
                await get_neo4j_client()
                self.neo4j_available = True
            except Exception as exc:
                logger.warning("Neo4j startup skipped: %s", exc)
                self.neo4j_available = False

        try:
            from ..core.intelligence_engine import get_intelligence_engine

            intelligence_engine = await get_intelligence_engine()
            self.intelligence_ready = intelligence_engine is not None

            background_scan_enabled = (
                os.getenv("INTELLIGENCE_BACKGROUND_SCAN_ENABLED", "false").lower() == "true"
            )
            if background_scan_enabled and intelligence_engine is not None:
                interval = int(os.getenv("INTELLIGENCE_SCAN_INTERVAL_MINUTES", "60"))
                await intelligence_engine.start_background_scanner(interval_minutes=interval)
        except Exception as exc:
            logger.warning("Intelligence engine startup skipped: %s", exc)
            self.intelligence_ready = False

        try:
            from ..integrations.llamaindex_rag import get_llamaindex_rag

            rag = await get_llamaindex_rag()
            self.rag_ready = rag is not None
        except Exception as exc:
            logger.warning("RAG startup skipped: %s", exc)
            self.rag_ready = False

        self.started = True

    async def shutdown(self) -> None:
        if not self.started:
            return

        try:
            from ..core.intelligence_engine import shutdown_intelligence_engine

            await shutdown_intelligence_engine()
        except Exception as exc:
            logger.warning("Intelligence shutdown warning: %s", exc)

        if self.neo4j_available:
            try:
                from ..integrations.neo4j_client import shutdown_neo4j

                await shutdown_neo4j()
            except Exception as exc:
                logger.warning("Neo4j shutdown warning: %s", exc)
            self.neo4j_available = False

        if self.redis is not None:
            try:
                await self.redis.aclose()
            except Exception as exc:
                logger.warning("Redis shutdown warning: %s", exc)
            self.redis = None

        try:
            await dispose_async_engine()
        except Exception as exc:
            logger.warning("DB engine shutdown warning: %s", exc)

        self.started = False
