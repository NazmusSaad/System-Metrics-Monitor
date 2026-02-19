"""Metrics collector — runs in background, stores samples to Postgres."""
import asyncio
import logging
import time
from datetime import datetime, timezone

import psutil

from app.database import async_session
from app.models import MetricsSample
from app.config import settings

logger = logging.getLogger(__name__)

# Keep previous network counters for rate calculation
_prev_net = None
_prev_time = None


def _collect_snapshot() -> dict:
    """Collect a single system metrics snapshot (sync, uses psutil)."""
    global _prev_net, _prev_time

    now = time.monotonic()
    cpu = psutil.cpu_percent(interval=None)

    # Load average (unavailable on Windows)
    try:
        load1 = psutil.getloadavg()[0]
    except (AttributeError, OSError):
        load1 = None

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Network rate
    net = psutil.net_io_counters()
    if _prev_net is not None and _prev_time is not None:
        dt = now - _prev_time if (now - _prev_time) > 0 else 1
        rx_bps = (net.bytes_recv - _prev_net.bytes_recv) / dt
        tx_bps = (net.bytes_sent - _prev_net.bytes_sent) / dt
    else:
        rx_bps = 0.0
        tx_bps = 0.0
    _prev_net = net
    _prev_time = now

    # Uptime
    try:
        uptime = now - 0  # psutil.boot_time gives epoch
        uptime = time.time() - psutil.boot_time()
    except Exception:
        uptime = None

    return {
        "ts_utc": datetime.now(timezone.utc),
        "cpu_percent": cpu,
        "load_avg_1": load1,
        "mem_used_bytes": mem.used,
        "mem_total_bytes": mem.total,
        "mem_percent": mem.percent,
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
        "disk_percent": disk.percent,
        "net_rx_bps": rx_bps,
        "net_tx_bps": tx_bps,
        "uptime_seconds": uptime,
    }


async def collector_loop(stop_event: asyncio.Event):
    """Collect metrics every COLLECTION_INTERVAL_SECONDS and persist."""
    interval = settings.collection_interval_seconds
    logger.info("Collector starting — interval=%ss", interval)

    # Prime CPU counter (first call always returns 0)
    psutil.cpu_percent(interval=None)

    while not stop_event.is_set():
        try:
            snapshot = await asyncio.get_event_loop().run_in_executor(None, _collect_snapshot)
            async with async_session() as session:
                session.add(MetricsSample(**snapshot))
                await session.commit()
        except Exception:
            logger.exception("Collector error")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass

    logger.info("Collector stopped")
