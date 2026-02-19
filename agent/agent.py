"""Metrics Monitor Agent — collects system metrics and sends to backend."""
import os
import sys
import time
import json
import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agent")

BACKEND_URL = os.environ.get("BACKEND_URL", "").rstrip("/")
INGEST_API_KEY = os.environ.get("INGEST_API_KEY", "")
HOST_KEY = os.environ.get("HOST_KEY", "")
INTERVAL = int(os.environ.get("INTERVAL_SECONDS", "2"))

if not BACKEND_URL:
    logger.error("BACKEND_URL is required")
    sys.exit(1)
if not HOST_KEY:
    logger.error("HOST_KEY is required")
    sys.exit(1)

_prev_net = None
_prev_time = None


def collect() -> dict:
    global _prev_net, _prev_time

    now = time.monotonic()
    cpu = psutil.cpu_percent(interval=None)

    try:
        load1 = psutil.getloadavg()[0]
    except (AttributeError, OSError):
        load1 = None

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    net = psutil.net_io_counters()
    if _prev_net is not None and _prev_time is not None:
        dt = max(now - _prev_time, 0.1)
        rx_bps = (net.bytes_recv - _prev_net.bytes_recv) / dt
        tx_bps = (net.bytes_sent - _prev_net.bytes_sent) / dt
    else:
        rx_bps = 0.0
        tx_bps = 0.0
    _prev_net = net
    _prev_time = now

    try:
        uptime = time.time() - psutil.boot_time()
    except Exception:
        uptime = None

    payload = {
        "host_key": HOST_KEY,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": cpu,
        "mem_used_bytes": mem.used,
        "mem_total_bytes": mem.total,
        "mem_percent": mem.percent,
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
        "disk_percent": disk.percent,
        "net_rx_bps": rx_bps,
        "net_tx_bps": tx_bps,
    }
    if load1 is not None:
        payload["load_avg_1"] = load1
    if uptime is not None:
        payload["uptime_seconds"] = uptime
    return payload


def send(payload: dict) -> bool:
    url = f"{BACKEND_URL}/api/ingest"
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if INGEST_API_KEY:
        headers["X-API-KEY"] = INGEST_API_KEY
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True
            logger.warning("Ingest returned %s", resp.status)
            return False
    except HTTPError as e:
        logger.error("Ingest HTTP error %s: %s", e.code, e.read().decode(errors="replace")[:200])
        return False
    except URLError as e:
        logger.error("Ingest connection error: %s", e.reason)
        return False


def main():
    logger.info("Agent starting — host_key=%s backend=%s interval=%ss", HOST_KEY, BACKEND_URL, INTERVAL)

    # Prime CPU counter
    psutil.cpu_percent(interval=None)

    backoff = 0
    while True:
        try:
            payload = collect()
            ok = send(payload)
            if ok:
                backoff = 0
                logger.debug("Sent sample for %s", HOST_KEY)
            else:
                backoff = min(backoff + 1, 5)
        except Exception:
            logger.exception("Agent error")
            backoff = min(backoff + 1, 5)

        sleep = INTERVAL + backoff * 2
        time.sleep(sleep)


if __name__ == "__main__":
    main()
