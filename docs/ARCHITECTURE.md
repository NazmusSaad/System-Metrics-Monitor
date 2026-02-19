# Architecture

## Overview

System Metrics Monitor is a three-service application:

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────▶│ Backend  │────▶│ Postgres │
│  (nginx) │     │ (FastAPI)│     │   (DB)   │
│ :3000    │     │ :8000    │     │ :5432    │
└──────────┘     └──────────┘     └──────────┘
```

## Components

### Backend (Python / FastAPI)

- **Collector loop**: An async background task spawned on startup that calls `psutil` every N seconds and writes a row to `metrics_samples`.
- **API routes**: Serve latest, historical (with bucket downsampling), and summary endpoints.
- **Health computation**: Computes OK/WARN/CRIT per metric based on configurable thresholds.

### Frontend (React / Vite / TypeScript)

- Single-page app with Recharts for interactive charts.
- Polls `/api/metrics/latest` every 2s when "Live" is enabled.
- Time range selector triggers new `/api/metrics` queries with appropriate step values.
- Nginx serves the built SPA and proxies `/api/` to the backend container.

### Database (PostgreSQL)

- Single table `metrics_samples` with a `ts_utc` index.
- Alembic manages schema migrations (auto-run on backend startup).
- Downsampling uses SQL `EXTRACT(EPOCH FROM ts_utc)` bucketing with `GROUP BY`.

## Data Flow

1. `psutil` collects host metrics → stored in `metrics_samples` table.
2. Frontend fetches from `/api/*` endpoints via nginx reverse proxy.
3. Historical queries use SQL bucket averaging to limit response size.

## Design Decisions

- **Single table**: Simple and sufficient for V1 single-node monitoring.
- **SQL downsampling**: Keeps the API fast without a separate aggregation pipeline.
- **Nginx proxy**: Frontend and API share the same origin, avoiding CORS in production.
- **Async SQLAlchemy**: Non-blocking DB access in the FastAPI event loop.
