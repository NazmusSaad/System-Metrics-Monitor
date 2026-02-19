# API Reference

All endpoints are under the `/api` prefix.

## Health

### `GET /api/health`

Returns service health status.

**Response** `200 OK`
```json
{ "status": "ok" }
```

---

## Latest Metrics

### `GET /api/metrics/latest`

Returns the most recent metrics sample with health badge.

**Response** `200 OK`
```json
{
  "id": 42,
  "ts_utc": "2025-01-15T12:00:00+00:00",
  "cpu_percent": 23.5,
  "load_avg_1": 1.2,
  "mem_used_bytes": 8589934592,
  "mem_total_bytes": 17179869184,
  "mem_percent": 50.0,
  "disk_used_bytes": 107374182400,
  "disk_total_bytes": 512110190592,
  "disk_percent": 21.0,
  "net_rx_bps": 1024.5,
  "net_tx_bps": 512.3,
  "uptime_seconds": 86400,
  "health": {
    "overall": "OK",
    "cpu": "OK",
    "mem": "OK",
    "disk": "OK"
  }
}
```

**Error** `404` — no data collected yet.

---

## Historical Range

### `GET /api/metrics?from=ISO8601&to=ISO8601&step=seconds`

Returns downsampled metric points over a time range.

| Param | Required | Default | Description |
|---|---|---|---|
| `from` | No | 1 hour ago | Start time (ISO 8601) |
| `to` | No | now | End time (ISO 8601) |
| `step` | No | 2 | Bucket size in seconds |

- Max 5000 points. If exceeded, `step` auto-increases and `note` explains.

**Response** `200 OK`
```json
{
  "points": [ /* array of MetricsSample objects */ ],
  "step_seconds": 10,
  "note": null
}
```

**Errors**
- `400` — invalid ISO 8601 format or `from >= to`.

---

## Summary

### `GET /api/summary?window=minutes`

Returns min/avg/max for key metrics over a time window.

| Param | Required | Default | Range |
|---|---|---|---|
| `window` | No | 60 | 1–1440 minutes |

**Response** `200 OK`
```json
{
  "window_minutes": 60,
  "cpu_percent": { "min": 5.0, "avg": 25.3, "max": 89.2 },
  "mem_percent": { "min": 40.0, "avg": 52.1, "max": 65.0 },
  "disk_percent": { "min": 20.9, "avg": 21.0, "max": 21.1 },
  "net_rx_bps": { "min": 0.0, "avg": 1024.0, "max": 50000.0 },
  "net_tx_bps": { "min": 0.0, "avg": 512.0, "max": 25000.0 }
}
```

**Error** `404` — no data in the requested window.
