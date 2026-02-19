"""API routes under /api."""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import MetricsSample
from app.schemas import (
    HealthResponse,
    LatestResponse,
    HealthBadge,
    MetricsSampleOut,
    MetricsRangeResponse,
    SummaryResponse,
    SummaryField,
)
from app.config import settings

router = APIRouter(prefix="/api")

MAX_POINTS = 5000


def _compute_health(sample: MetricsSample) -> HealthBadge:
    def _level(value, warn, crit):
        if value >= crit:
            return "CRIT"
        if value >= warn:
            return "WARN"
        return "OK"

    cpu = _level(sample.cpu_percent, settings.cpu_warn, settings.cpu_crit)
    mem = _level(sample.mem_percent, settings.mem_warn, settings.mem_crit)
    disk = _level(sample.disk_percent, settings.disk_warn, settings.disk_crit)

    worst = "OK"
    for s in (cpu, mem, disk):
        if s == "CRIT":
            worst = "CRIT"
            break
        if s == "WARN":
            worst = "WARN"

    return HealthBadge(overall=worst, cpu=cpu, mem=mem, disk=disk)


# ---------- 1) Health ----------
@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


# ---------- 2) Latest ----------
@router.get("/metrics/latest", response_model=LatestResponse)
async def metrics_latest(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(MetricsSample).order_by(MetricsSample.ts_utc.desc()).limit(1)
    )
    sample = result.scalar_one_or_none()
    if sample is None:
        raise HTTPException(status_code=404, detail="No metrics collected yet")
    badge = _compute_health(sample)
    data = MetricsSampleOut.model_validate(sample).model_dump()
    return LatestResponse(**data, health=badge)


# ---------- 3) Historical range ----------
def _parse_iso(value: str, name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid ISO8601 for '{name}': {value}")


@router.get("/metrics", response_model=MetricsRangeResponse)
async def metrics_range(
    session: AsyncSession = Depends(get_session),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = None,
    step: Optional[int] = None,
):
    now = datetime.now(timezone.utc)
    ts_from = _parse_iso(from_, "from") if from_ else now - timedelta(hours=1)
    ts_to = _parse_iso(to, "to") if to else now

    if ts_from >= ts_to:
        raise HTTPException(status_code=400, detail="'from' must be before 'to'")

    step_seconds = step if step and step >= 1 else 2

    # Estimate number of points
    range_seconds = (ts_to - ts_from).total_seconds()
    estimated_points = range_seconds / step_seconds
    note = None
    if estimated_points > MAX_POINTS:
        step_seconds = max(int(range_seconds / MAX_POINTS), 1)
        note = f"Step auto-increased to {step_seconds}s to stay within {MAX_POINTS} point limit."

    # SQL bucket averaging
    query = text("""
        SELECT
            (EXTRACT(EPOCH FROM ts_utc)::bigint / :step) * :step AS bucket,
            AVG(cpu_percent) AS cpu_percent,
            AVG(load_avg_1) AS load_avg_1,
            AVG(mem_used_bytes) AS mem_used_bytes,
            AVG(mem_total_bytes) AS mem_total_bytes,
            AVG(mem_percent) AS mem_percent,
            AVG(disk_used_bytes) AS disk_used_bytes,
            AVG(disk_total_bytes) AS disk_total_bytes,
            AVG(disk_percent) AS disk_percent,
            AVG(net_rx_bps) AS net_rx_bps,
            AVG(net_tx_bps) AS net_tx_bps,
            AVG(uptime_seconds) AS uptime_seconds
        FROM metrics_samples
        WHERE ts_utc >= :ts_from AND ts_utc <= :ts_to
        GROUP BY bucket
        ORDER BY bucket
    """)

    result = await session.execute(query, {
        "step": step_seconds,
        "ts_from": ts_from,
        "ts_to": ts_to,
    })
    rows = result.fetchall()

    points = []
    for i, row in enumerate(rows):
        points.append(MetricsSampleOut(
            id=i,
            ts_utc=datetime.fromtimestamp(row.bucket, tz=timezone.utc),
            cpu_percent=round(row.cpu_percent, 2),
            load_avg_1=round(row.load_avg_1, 2) if row.load_avg_1 is not None else None,
            mem_used_bytes=row.mem_used_bytes,
            mem_total_bytes=row.mem_total_bytes,
            mem_percent=round(row.mem_percent, 2),
            disk_used_bytes=row.disk_used_bytes,
            disk_total_bytes=row.disk_total_bytes,
            disk_percent=round(row.disk_percent, 2),
            net_rx_bps=round(row.net_rx_bps, 2),
            net_tx_bps=round(row.net_tx_bps, 2),
            uptime_seconds=row.uptime_seconds,
        ))

    return MetricsRangeResponse(points=points, step_seconds=step_seconds, note=note)


# ---------- 4) Summary ----------
@router.get("/summary", response_model=SummaryResponse)
async def summary(
    session: AsyncSession = Depends(get_session),
    window: int = Query(60, ge=1, le=1440),
):
    since = datetime.now(timezone.utc) - timedelta(minutes=window)

    query = select(
        func.min(MetricsSample.cpu_percent),
        func.avg(MetricsSample.cpu_percent),
        func.max(MetricsSample.cpu_percent),
        func.min(MetricsSample.mem_percent),
        func.avg(MetricsSample.mem_percent),
        func.max(MetricsSample.mem_percent),
        func.min(MetricsSample.disk_percent),
        func.avg(MetricsSample.disk_percent),
        func.max(MetricsSample.disk_percent),
        func.min(MetricsSample.net_rx_bps),
        func.avg(MetricsSample.net_rx_bps),
        func.max(MetricsSample.net_rx_bps),
        func.min(MetricsSample.net_tx_bps),
        func.avg(MetricsSample.net_tx_bps),
        func.max(MetricsSample.net_tx_bps),
    ).where(MetricsSample.ts_utc >= since)

    result = await session.execute(query)
    row = result.one()

    if row[0] is None:
        raise HTTPException(status_code=404, detail="No data for this window")

    def sf(i):
        return SummaryField(min=round(row[i], 2), avg=round(row[i + 1], 2), max=round(row[i + 2], 2))

    return SummaryResponse(
        window_minutes=window,
        cpu_percent=sf(0),
        mem_percent=sf(3),
        disk_percent=sf(6),
        net_rx_bps=sf(9),
        net_tx_bps=sf(12),
    )
