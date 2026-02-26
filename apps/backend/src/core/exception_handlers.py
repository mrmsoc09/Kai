from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


logger = logging.getLogger("k1.exceptions")


def _log_exception(
    request: Request,
    exc: Exception,
    *,
    status_code: int,
    error_code: str,
) -> str:
    error_id = str(uuid4())
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "error_id": error_id,
        "status_code": status_code,
        "error_code": error_code,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "path": request.url.path,
        "method": request.method,
    }
    logger.error(json.dumps(payload, ensure_ascii=False))
    return error_id


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TimeoutError)
    async def _timeout_handler(request: Request, exc: TimeoutError):
        error_id = _log_exception(
            request,
            exc,
            status_code=504,
            error_code="operation_timeout",
        )
        return JSONResponse(
            status_code=504,
            content={"detail": "operation_timeout", "error_id": error_id},
        )

    @app.exception_handler(ValueError)
    async def _value_error_handler(request: Request, exc: ValueError):
        error_id = _log_exception(
            request,
            exc,
            status_code=422,
            error_code="invalid_value",
        )
        return JSONResponse(
            status_code=422,
            content={"detail": "invalid_value", "error_id": error_id},
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error_handler(request: Request, exc: IntegrityError):
        error_id = _log_exception(
            request,
            exc,
            status_code=409,
            error_code="integrity_violation",
        )
        return JSONResponse(
            status_code=409,
            content={"detail": "integrity_violation", "error_id": error_id},
        )

    @app.exception_handler(SQLAlchemyError)
    async def _sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        error_id = _log_exception(
            request,
            exc,
            status_code=500,
            error_code="database_error",
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "database_error", "error_id": error_id},
        )

    @app.exception_handler(Exception)
    async def _generic_exception_handler(request: Request, exc: Exception):
        error_id = _log_exception(
            request,
            exc,
            status_code=500,
            error_code="internal_server_error",
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "internal_server_error", "error_id": error_id},
        )

