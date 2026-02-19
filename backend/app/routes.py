"""API routes under /api."""
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import MetricsSample, Host
from app.schemas import (
    HealthResponse,
    LatestResponse,
    HealthBadge,
    MetricsSampleOut,
    MetricsRangeResponse,
    SummaryResponse,
    SummaryField,
    IngestPayload,
    IngestResponse,
    HostOut,
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


async def _resolve_host_id(session: AsyncSession, host_key: Optional[str]) -> Optional[int]:
    """Resolve host_key to host_id. Returns None if no host_key given (show all)."""
    if not host_key:
        return None
    result = await session.execute(select(Host.id).where(Host.host_key == host_key))
    host_id = result.scalar_one_or_none()
    if host_id is None:
        raise HTTPException(status_code=404, detail=f"Host '{host_key}' not found")
    return host_id


# ---------- 1) Health ----------
@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


# ---------- 2) Latest ----------
@router.get("/metrics/latest", response_model=LatestResponse)
async def metrics_latest(
    session: AsyncSession = Depends(get_session),
    host_key: Optional[str] = Query(None),
):
    q = select(MetricsSample).order_by(MetricsSample.ts_utc.desc()).limit(1)
    host_id = await _resolve_host_id(session, host_key)
    if host_id is not None:
        q = q.where(MetricsSample.host_id == host_id)

    result = await session.execute(q)
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
    host_key: Optional[str] = Query(None),
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

    host_id = await _resolve_host_id(session, host_key)

    # SQL bucket averaging with optional host filter
    host_clause = "AND host_id = :host_id" if host_id is not None else ""
    query = text(f"""
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
        WHERE ts_utc >= :ts_from AND ts_utc <= :ts_to {host_clause}
        GROUP BY bucket
        ORDER BY bucket
    """)

    params = {"step": step_seconds, "ts_from": ts_from, "ts_to": ts_to}
    if host_id is not None:
        params["host_id"] = host_id

    result = await session.execute(query, params)
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
    host_key: Optional[str] = Query(None),
):
    since = datetime.now(timezone.utc) - timedelta(minutes=window)
    host_id = await _resolve_host_id(session, host_key)

    q = select(
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

    if host_id is not None:
        q = q.where(MetricsSample.host_id == host_id)

    result = await session.execute(q)
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


# ---------- 5) Hosts list (V2) ----------
@router.get("/hosts", response_model=List[HostOut])
async def list_hosts(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Host).order_by(Host.last_seen_at.desc())
    )
    return result.scalars().all()


# ---------- 6) Ingest (V2) ----------
def _check_api_key(x_api_key: Optional[str] = Header(None)):
    expected = settings.ingest_api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    payload: IngestPayload,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_check_api_key),
):
    now = datetime.now(timezone.utc)

    # Upsert host
    result = await session.execute(
        select(Host).where(Host.host_key == payload.host_key)
    )
    host = result.scalar_one_or_none()
    if host is None:
        host = Host(
            host_key=payload.host_key,
            display_name=payload.host_key,
            last_seen_at=now,
        )
        session.add(host)
        await session.flush()
    else:
        host.last_seen_at = now

    sample = MetricsSample(
        host_id=host.id,
        ts_utc=payload.ts_utc or now,
        cpu_percent=payload.cpu_percent,
        load_avg_1=payload.load_avg_1,
        mem_used_bytes=payload.mem_used_bytes,
        mem_total_bytes=payload.mem_total_bytes,
        mem_percent=payload.mem_percent,
        disk_used_bytes=payload.disk_used_bytes,
        disk_total_bytes=payload.disk_total_bytes,
        disk_percent=payload.disk_percent,
        net_rx_bps=payload.net_rx_bps,
        net_tx_bps=payload.net_tx_bps,
        uptime_seconds=payload.uptime_seconds,
    )
    session.add(sample)
    await session.commit()
    await session.refresh(sample)

    return IngestResponse(status="ok", host_key=payload.host_key, sample_id=sample.id)
