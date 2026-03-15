"""
Correlation ID Middleware
Propagates or generates a UUID per request so that all log entries and error
responses can be traced back to a single inbound call.
"""

from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_HEADER = "X-Request-ID"
_ID_REGEX = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Reads X-Request-ID from the inbound request (if present) or generates a new
    UUID4.  The ID is stored on ``request.state.correlation_id`` and echoed back
    in the response header so clients can correlate their logs with server logs.
    """

    async def dispatch(self, request: Request, call_next):
        client_id = request.headers.get(_HEADER)
        
        # Validate client-supplied correlation ID
        if client_id and _ID_REGEX.match(client_id):
            correlation_id = client_id
        else:
            # Discard invalid or missing client ID and generate a fresh UUID
            correlation_id = str(uuid.uuid4())
            
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers[_HEADER] = correlation_id
        return response
