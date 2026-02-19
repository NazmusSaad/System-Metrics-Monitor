"""Pydantic schemas for API responses."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class MetricsSampleOut(BaseModel):
    id: int
    ts_utc: datetime
    cpu_percent: float
    load_avg_1: Optional[float] = None
    mem_used_bytes: float
    mem_total_bytes: float
    mem_percent: float
    disk_used_bytes: float
    disk_total_bytes: float
    disk_percent: float
    net_rx_bps: float
    net_tx_bps: float
    uptime_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str


class HealthBadge(BaseModel):
    overall: str  # OK, WARN, CRIT
    cpu: str
    mem: str
    disk: str


class LatestResponse(MetricsSampleOut):
    health: HealthBadge


class MetricsRangeResponse(BaseModel):
    points: List[MetricsSampleOut]
    step_seconds: int
    note: Optional[str] = None


class SummaryField(BaseModel):
    min: float
    avg: float
    max: float


class SummaryResponse(BaseModel):
    window_minutes: int
    cpu_percent: SummaryField
    mem_percent: SummaryField
    disk_percent: SummaryField
    net_rx_bps: SummaryField
    net_tx_bps: SummaryField
