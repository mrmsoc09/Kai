"""
Log Watchdog API Schemas
Pydantic models for watchdog endpoints
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class AlertSummary(BaseModel):
    """Summary of a single alert"""
    alert_id: str = Field(..., description="Unique alert identifier")
    log_id: str = Field(..., description="Associated log entry ID")
    operation: str = Field(..., description="Operation type (e.g., exploitation, reconnaissance)")
    severity: str = Field(..., description="Alert severity level: critical, high, medium, info")
    message: str = Field(..., description="Alert message")
    detected_at: str = Field(..., description="ISO timestamp when alert was detected")
    action_required: str = Field(..., description="Required remediation action")


class ScanResults(BaseModel):
    """Results of a log scan operation"""
    total_logs: int = Field(..., description="Total number of logs scanned")
    signed_logs: int = Field(..., description="Number of logs with valid signatures")
    unsigned_logs: int = Field(..., description="Number of logs without signatures")
    signature_coverage: float = Field(..., description="Percentage of logs with valid signatures")


class ScanResponse(BaseModel):
    """Response from scan endpoint"""
    success: bool
    scan_results: ScanResults
    alerts: List[AlertSummary] = Field(default_factory=list)
    new_alerts_count: int
    timestamp: Optional[str]


class LogCoverage(BaseModel):
    """Log signature coverage statistics"""
    total_logs: int
    signed_logs: int
    unsigned_logs: int
    signature_coverage: float


class AlertBreakdown(BaseModel):
    """Alert statistics by severity"""
    total: int
    critical: int
    high: int
    medium: int
    info: int


class AlertDetail(BaseModel):
    """Detailed alert information"""
    alert_id: str
    operation: str
    severity: str
    message: str
    action: str


class WatchdogReport(BaseModel):
    """Comprehensive watchdog report"""
    scan_timestamp: Optional[str]
    summary: Dict[str, Any]
    alerts: AlertBreakdown
    alert_details: List[AlertDetail]
    status: str = Field(..., description="Overall status: CRITICAL, WARNING, or NORMAL")


class ReportResponse(BaseModel):
    """Response from report endpoint"""
    success: bool
    report: WatchdogReport


class RemediationResults(BaseModel):
    """Results of remediation attempt"""
    unsigned: int = Field(..., description="Number of unsigned logs found")
    signed: int = Field(..., description="Number of logs successfully signed")
    failed: int = Field(..., description="Number of signing attempts that failed")


class RemediationResponse(BaseModel):
    """Response from remediation endpoint"""
    success: bool
    remediation_results: RemediationResults
    timestamp: Optional[str]


class AlertList(BaseModel):
    """List of alerts"""
    success: bool
    total_alerts: int = Field(..., description="Total alerts in system")
    filtered_alerts: int = Field(..., description="Number of alerts in this response")
    alerts: List[AlertSummary]


class LogMonitoring(BaseModel):
    """Log monitoring statistics"""
    total_logs: int
    signed_logs: int
    unsigned_logs: int
    coverage: float


class AlertStats(BaseModel):
    """Alert statistics"""
    total: int
    critical: int
    high: int
    medium: int
    info: int


class WatchdogStatus(BaseModel):
    """Watchdog system status"""
    overall_status: str = Field(..., description="CRITICAL, WARNING, or NORMAL")
    log_monitoring: LogMonitoring
    alerts: AlertStats
    last_scan: Optional[str]
    crypto_system_available: bool
    critical_operations: List[str]


class StatusResponse(BaseModel):
    """Response from status endpoint"""
    success: bool
    status: WatchdogStatus


class ClearAlertResponse(BaseModel):
    """Response from alert clearing endpoint"""
    success: bool
    message: str
    alerts_remaining: int


class InitResponse(BaseModel):
    """Response from initialization endpoint"""
    success: bool
    message: str
    config: Dict[str, Any]


class CryptoSystemResponse(BaseModel):
    """Response from crypto system configuration endpoint"""
    success: bool
    message: str
    crypto_system_available: bool
