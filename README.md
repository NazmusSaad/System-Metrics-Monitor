# System Metrics Monitor

A self-hostable, real-time system metrics dashboard with multi-device monitoring support. Track CPU, memory, disk, and network across multiple machines from a single dashboard.

**Live Demo:** [system-metrics-monitor.vercel.app](https://system-metrics-monitor.vercel.app/)

## UI Preview

![App screenshot](https://github.com/NazmusSaad/System-Metrics-Monitor/blob/master/system_metrics_v1_pic3.png)
![App screenshot](https://github.com/NazmusSaad/System-Metrics-Monitor/blob/master/system_metrics_v1_pic2.png)

## Features

- **Real-time dashboard** — CPU, memory, disk, and network charts with 2s live polling
- **Multi-device monitoring** — deploy lightweight agents on remote machines, view all hosts from one dashboard
- **Host selector** — switch between monitored devices via dropdown
- **Health badges** — OK / WARN / CRIT status based on configurable thresholds
- **Historical data** — query any time range with automatic downsampling (max 5000 points)
- **Summary stats** — min / avg / max over configurable windows
- **Zero external dependencies** — runs entirely in Docker, no paid SaaS required

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

## Architecture

```
┌──────────────┐      POST /api/ingest       ┌───────────┐       ┌────────────┐
│  Agent (N)   │ ──────────────────────────►  │  Backend  │ ◄───► │  Postgres  │
│  (remote)    │     X-API-KEY header         │  FastAPI  │       │            │
└──────────────┘                              └─────┬─────┘       └────────────┘
                                                    │
                                Local collector     │  GET /api/*
                                (optional)          │
                                                    ▼
                                              ┌───────────┐
                                              │ Frontend   │
                                              │ React+Vite │
                                              └───────────┘
```

The backend collects local metrics by default and also accepts metrics from remote **agents** via `POST /api/ingest`. The frontend queries all data through the REST API and includes a host selector to switch between devices.

## Multi-Device Monitoring

### 1. Set an API key on the backend

Add to your `.env`:

```
INGEST_API_KEY=your-secret-key
```

### 2. Deploy an agent on each remote device

```bash
# On the remote machine
docker build -t metrics-agent ./agent

docker run -d --name metrics-agent --pid=host \
  -e BACKEND_URL=https://your-backend.example.com \
  -e INGEST_API_KEY=your-secret-key \
  -e HOST_KEY=my-server-1 \
  metrics-agent
```

Or use the provided compose file:

```bash
# Linux/macOS
docker compose -f docker-compose.agent.yml up --build -d

# Windows
docker compose -f docker-compose.agent.windows.yml up --build -d
```

### Agent Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BACKEND_URL` | Yes | — | Backend URL (e.g., `https://your-app.onrender.com`) |
| `INGEST_API_KEY` | If set on backend | — | Must match backend's `INGEST_API_KEY` |
| `HOST_KEY` | Yes | — | Unique identifier for this device |
| `INTERVAL_SECONDS` | No | `2` | Collection interval in seconds |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `metrics` | Postgres username |
| `POSTGRES_PASSWORD` | `metricspass` | Postgres password |
| `POSTGRES_DB` | `metrics_monitor` | Postgres database name |
| `DATABASE_URL` | (see .env.example) | Full async connection string |
| `COLLECTION_INTERVAL_SECONDS` | `2` | How often to sample metrics |
| `MACHINE_NAME` | `local` | Display name for the local host |
| `CPU_WARN` / `CPU_CRIT` | `80` / `95` | CPU health thresholds |
| `MEM_WARN` / `MEM_CRIT` | `80` / `95` | Memory health thresholds |
| `DISK_WARN` / `DISK_CRIT` | `85` / `95` | Disk health thresholds |
| `INGEST_API_KEY` | (empty) | API key for agent auth — empty disables auth |
| `ENABLE_LOCAL_COLLECTOR` | `true` | Set `false` to disable local metric collection |

## API Endpoints

All endpoints are under `/api`. Existing V1 endpoints now accept an optional `?host_key=` query parameter to filter by device.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/metrics/latest?host_key=` | Latest sample with health badge |
| `GET` | `/api/metrics?from=&to=&step=&host_key=` | Historical range with downsampling |
| `GET` | `/api/summary?window=&host_key=` | Min/avg/max summary stats |
| `GET` | `/api/hosts` | List all registered hosts |
| `POST` | `/api/ingest` | Submit metrics from an agent (X-API-KEY header) |

See [docs/API.md](docs/API.md) for detailed request/response examples.

## Migrations

Alembic migrations run **automatically** on backend startup. No manual steps needed.

```bash
# Manual run (if needed)
docker compose exec backend alembic upgrade head
```

## Backward Compatibility

- `host_id` is nullable — existing V1 data continues to work without modification
- Omitting `?host_key=` returns data across all hosts (V1 behavior)
- Local collector runs by default (`ENABLE_LOCAL_COLLECTOR=true`)
- Empty `INGEST_API_KEY` disables auth (V1 default)

## Project Structure

```
metrics-monitor/
├── backend/                       # FastAPI + psutil + SQLAlchemy
│   ├── app/                       # Config, models, routes, collector
│   ├── alembic/                   # Database migrations
│   └── Dockerfile
├── frontend/                      # React + Vite + TypeScript + Tailwind + Recharts
│   └── Dockerfile
├── agent/                         # Lightweight remote metrics agent
│   ├── agent.py                   # psutil collector + HTTP sender
│   └── Dockerfile
├── docs/                          # Architecture & API docs
├── docker-compose.yml             # Main stack (backend + frontend + db)
├── docker-compose.agent.yml       # Agent compose (Linux/macOS)
├── docker-compose.agent.windows.yml  # Agent compose (Windows)
├── .env.example
└── README.md
```

## Deploy

### Docker Compose on a VPS

1. Copy the repo to your server
2. Edit `.env` with strong `POSTGRES_PASSWORD` and `INGEST_API_KEY`
3. Run `docker compose up -d --build`
4. (Optional) Put nginx/Caddy in front for HTTPS

### Railway / Render / Fly.io

Each service (frontend, backend, db) can be deployed as a separate service on any Docker-capable PaaS. Set environment variables in the platform dashboard.

### Azure (Container Apps + Azure Postgres)

Deploy the backend to Azure Container Apps with a managed PostgreSQL database:

```powershell
# Automated (PowerShell)
.\infra\azure\deploy.ps1

# Or follow the full step-by-step guide
```

See **[docs/AZURE_DEPLOY.md](docs/AZURE_DEPLOY.md)** for the complete Azure CLI deployment guide, including ACR image publishing, SSL configuration, agent setup, and cost estimates.
