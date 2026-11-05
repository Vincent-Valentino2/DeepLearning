# Movie Popularity & Recommendation App

A web app for exploring movie information and estimating whether a film is likely to be popular. It uses a machine learning model with movie metadata such as genres, release year, runtime, language, and budget.

The app includes:

- Movie search and curated movie picks
- Popularity predictions with feature explanations
- Side-by-side movie comparison
- Prediction history and analytics
- A personal movie watchlist

## Project structure

Each app layer has a dedicated directory and Docker Compose service. This keeps frontend, backend, and database changes easier to review and rebuild independently.

```text
.
├── frontend/          # React, TypeScript, Vite, and Nginx
├── backend/           # FastAPI API, prediction model, and backend Dockerfile
├── database/          # PostgreSQL initialization SQL
├── data/              # Sample data and local movie catalog files
├── docker-compose.yml # Runs the app services together
└── README.md
```

```text
Browser ──> frontend (Nginx, port 3000)
                │ /api requests
                ▼
            backend (FastAPI, port 8001)
                │ prediction analytics
                ▼
            database (PostgreSQL, port 5432)
```

The frontend, backend, and database are separate containers. Compose connects them on a private network. PostgreSQL data is stored in a named Docker volume, while backend catalog and local SQLite files are kept in the host `data/` directory. The SQL in `database/init.sql` runs when PostgreSQL first initializes its data directory.

## What you need

### To run with Docker (recommended)

- Docker Desktop, or Docker Engine with the Docker Compose plugin
- Git, to clone the repository
- Available local ports: `3000`, `8001`, and `5432`

Docker builds the frontend and backend images and starts PostgreSQL. Node.js and Python do not need to be installed on the host for this option.

### To run in local development mode

- Node.js 22 or newer and pnpm 9
- Python 3.12
- PostgreSQL is optional for local development; prediction analytics can use the backend's SQLite fallback

## Start the app with Docker

From the repository root, build and start all services:

```bash
docker compose up --build -d
```

Open the app at <http://localhost:3000>. The backend API documentation is at <http://localhost:8001/docs> and its health endpoint is <http://localhost:8001/api/health>.

Useful commands:

```bash
# Show service status
docker compose ps

# Follow logs from all services
docker compose logs -f

# Follow logs from one service
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f database

# Rebuild and restart one service after changing it
docker compose up --build -d frontend
docker compose up --build -d backend

# Start or recreate PostgreSQL after changing its Compose settings
docker compose up -d database

# Stop services and keep database data
docker compose down

# Stop services and permanently remove the PostgreSQL volume
docker compose down -v
```

`docker compose down -v` deletes PostgreSQL's stored data. Use `docker compose down` for normal shutdowns. The backend's `data/` files are stored separately on the host.

## Start in local development mode

Run the backend and frontend in separate terminals from the repository root.

Terminal 1, start the API:

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

Terminal 2, start the web app:

```bash
cd frontend
pnpm install
pnpm dev
```

Open <http://localhost:5174>. Vite proxies `/api` calls to the backend on port `8001`.

## Main service responsibilities

| Service | Directory | Responsibility |
| --- | --- | --- |
| Frontend | `frontend/` | Movie browsing, prediction forms, comparison, history, and watchlist UI |
| Backend | `backend/` | FastAPI endpoints, model inference, movie search, and application logic |
| Database | `database/` | PostgreSQL schema initialization; persistent database files are managed by Docker volume `pgdata` |

Compose service names are `frontend`, `backend`, and `database`. Rebuild the frontend or backend with `docker compose up --build -d <service>` after changing its code. PostgreSQL uses the official image; its initialization script only runs when the data volume is first created.
