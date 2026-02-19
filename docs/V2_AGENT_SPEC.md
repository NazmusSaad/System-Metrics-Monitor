# V2: Multi-Device Monitoring via Docker Agent (Minimal Spec)

## Goal
Enable monitoring multiple devices by running a lightweight Docker “agent” on each device. The agent collects local system metrics and sends them to the existing backend, which stores metrics per host and exposes host-aware APIs. Frontend adds a host selector.

## Constraints (non-negotiable)
- Keep existing V1 behavior working.
- Do NOT remove V1 collector loop yet; instead add a config flag to disable it in production if desired.
- No microservices, no message queue, no service discovery.
- Security: require an API key for ingestion.
- Avoid over-engineering. Minimal schema changes.

## Backend Changes
### 1) Authentication for ingestion
- Add env var: `INGEST_API_KEY` (required in production).
- Agent must send header: `X-API-KEY: <key>`.
- Backend rejects ingestion with 401 if missing/incorrect.

### 2) Host model
- Add table `hosts`:
  - id (uuid or bigserial)
  - host_key (string, unique)  // stable identifier sent by agent (e.g., "saaim-laptop")
  - display_name (string)
  - created_at (ts)
  - last_seen_at (ts)
- Update `metrics_samples` to include `host_id` foreign key.
- Add index on `(host_id, ts_utc)`.

### 3) Ingest endpoint
- `POST /api/ingest`
- Body: metrics payload including:
  - host_key (string)
  - ts_utc (optional; backend can set server time)
  - cpu_percent
  - mem_used_bytes, mem_total_bytes, mem_percent
  - disk_used_bytes, disk_total_bytes, disk_percent
  - net_rx_bps, net_tx_bps
  - uptime_seconds (optional)
- Behavior:
  - Upsert/find host by `host_key`
  - Update `last_seen_at`
  - Insert metrics sample

### 4) Host listing endpoint
- `GET /api/hosts` -> list hosts with last_seen_at, display_name, host_key

### 5) Make existing metrics endpoints host-aware (backwards compatible)
- Existing endpoints should accept optional `host_key` query param.
  - If not provided, default to "local" host (or first host) to preserve behavior.
- Update:
  - `GET /api/metrics/latest?host_key=...`
  - `GET /api/metrics?from=...&to=...&step=...&host_key=...`
  - `GET /api/summary?window=...&host_key=...`

### 6) Config: disable local collector when using agents
- Add env var: `ENABLE_LOCAL_COLLECTOR` default `true`
- In Render production, set it to `false` so only agents report.

### 7) Migrations
- Update Alembic migrations accordingly.

## Agent (Docker) — New Folder: /agent
Create an agent package that can be run as a container on any machine.

### Requirements
- Python 3.11
- psutil
- Reads env vars:
  - `BACKEND_URL` (e.g., https://system-metrics-monitor.onrender.com)
  - `INGEST_API_KEY`
  - `HOST_KEY` (unique stable id for this machine, ex: "laptop-1")
  - `INTERVAL_SECONDS` default 2
- Collect metrics every interval and POST to `${BACKEND_URL}/api/ingest`
- Compute network bytes/sec by sampling counters across intervals.
- Log success/failure; retry on network errors (simple backoff).
- Provide `agent/Dockerfile` and optionally a `docker-compose.agent.yml` example.

## Frontend Changes
- Add host selector dropdown (top bar):
  - fetch `/api/hosts`
  - select a host (default to first host or "local")
- Pass `host_key` to API calls.
- Display host name somewhere in header.

## Acceptance Criteria
- Vercel frontend can select between multiple hosts and charts update accordingly.
- Running agent container on two devices shows two hosts on dashboard.
- Ingest endpoint rejects requests without correct API key.
- Local dev still works with local collector enabled.
