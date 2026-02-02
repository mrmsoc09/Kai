"""
Common response schemas for API responses
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime


class Response(BaseModel):
    """Standard API response schema"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status_code: int = 200

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {},
                "error": None,
                "message": None,
                "timestamp": "2025-02-02T00:00:00",
                "status_code": 200,
            }
        }


class ErrorResponse(BaseModel):
    """Error response schema"""
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status_code: int = 500

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Internal server error",
                "details": {},
                "timestamp": "2025-02-02T00:00:00",
                "status_code": 500,
            }
        }
