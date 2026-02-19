# System Metrics Monitor

A self-hostable dashboard that monitors your machine's CPU, memory, disk, and network metrics in real time with historical charts.

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- No other dependencies required — everything runs in containers.

## Quick Start

```bash
# 1. Clone and enter the repo
cd metrics-monitor

# 2. Copy the env file
cp .env.example .env

# 3. Build and run
docker compose up --build
```

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `metrics` | Postgres username |
| `POSTGRES_PASSWORD` | `metricspass` | Postgres password |
| `POSTGRES_DB` | `metrics_monitor` | Postgres database name |
| `DATABASE_URL` | (see .env.example) | Full async connection string |
| `COLLECTION_INTERVAL_SECONDS` | `2` | How often to sample metrics |
| `MACHINE_NAME` | `local` | Display name in dashboard |
| `CPU_WARN` / `CPU_CRIT` | `80` / `95` | CPU health thresholds |
| `MEM_WARN` / `MEM_CRIT` | `80` / `95` | Memory health thresholds |
| `DISK_WARN` / `DISK_CRIT` | `85` / `95` | Disk health thresholds |

## Migrations

Alembic migrations run **automatically** on backend startup (`alembic upgrade head` in the Dockerfile CMD). No manual steps needed.

To run manually:

```bash
docker compose exec backend alembic upgrade head
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design details.

## API Reference

See [docs/API.md](docs/API.md) for endpoint documentation.

## Deploy Options

### Option 1: Docker Compose on a VPS

1. Copy the repo to your server.
2. Edit `.env` with a strong `POSTGRES_PASSWORD`.
3. Run `docker compose up -d --build`.
4. (Optional) Put nginx/Caddy in front for HTTPS.

### Option 2: Railway / Render / Fly.io

Each service (frontend, backend, db) can be deployed as a separate service on any Docker-capable PaaS. Set environment variables in the platform dashboard.

## Project Structure

```
metrics-monitor/
├── backend/           # FastAPI + psutil + SQLAlchemy
│   ├── app/           # Application code
│   ├── alembic/       # Database migrations
│   └── Dockerfile
├── frontend/          # React + Vite + TypeScript + Tailwind + Recharts
│   └── Dockerfile
├── docs/              # Architecture & API docs
├── docker-compose.yml
├── .env.example
└── README.md
```
