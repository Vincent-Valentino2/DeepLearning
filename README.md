# Movie Popularity & Recommendation App

[![CI/CD Pipeline](https://github.com/Vincent-Valentino2/DeepLearning/actions/workflows/ci-cd.yml/badge.svg?branch=main)](https://github.com/Vincent-Valentino2/DeepLearning/actions/workflows/ci-cd.yml)

A web app for exploring movie information and estimating whether a film is likely to be popular. It uses a machine learning model with movie metadata such as genres, release year, runtime, language, and budget.

The app includes:

- Movie search and curated movie picks
- Popularity predictions with feature explanations
- Side-by-side movie comparison
- Prediction history and analytics
- A personal movie watchlist
- A live environment status bar for the frontend, backend, and database containers

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

To show the deployed commit and release tag in the UI footer, pass them as build arguments:

```bash
GIT_COMMIT_SHA=$(git rev-parse HEAD) RELEASE_ENV=staging docker compose up --build -d
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

## Model training and evaluation

The model is a scikit-learn MLP (62 features, layers 128-64-32). Training is reproducible: the candidate pool is deduplicated, sampled with seed 42, split 80/20 with stratification, and the label threshold, scalers, and curated anchor films come from the training split only.

```bash
# Retrain and write backend/models/mlp_model.joblib + backend/models/evaluation.json
backend/.venv/bin/python -m backend.data_processor

# Ablations, hyperparameter variants, and baselines over 5 seeds -> backend/models/experiments.json
backend/.venv/bin/python -m backend.experiments
```

Both commands need the local catalog `data/movies.db` (built from the Kaggle CSV by `backend/build_index.py`). `scikit-learn` is pinned to the version that serialized the model.

## Environment health and release status

The header shows a status bar that polls every 10 seconds:

| Indicator | Source |
| --- | --- |
| Frontend | The server that delivered the page (Nginx in Docker, Vite in dev) and its port |
| Backend | Round-trip latency of `GET /api/health` |
| PostgreSQL | `database` block of `/api/health`, which runs `SELECT 1` on a fresh connection |

`/api/health` returns `"status": "degraded"` with HTTP 200 when the API is up but the database is unreachable, so the backend container is not restarted for a database outage. Its `release` block reports the commit SHA and environment the backend was built with.

The footer shows the commit the frontend was built from (linked to GitHub), the release environment tag, and the live CI/CD badge. Without build arguments, local builds use the checkout's current commit and `development` (dev server) or `production` (build) as the tag.

## CI/CD and branch protection

[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) runs on every push and pull request to `main`:

1. **Frontend Lint & Build Check**: typecheck and production build
2. **Backend Syntax & Health Verification**: import check and backend unit tests
3. **Docker Multi-Container Build Verification**: builds both images, starts all three containers with Compose, and checks that the frontend, `/api/health`, and PostgreSQL are reachable
4. **Publish Container Images (GHCR)**: pushes to `main` only; pushes the frontend and backend images tagged with the commit SHA and `latest`
5. **Deploy to Production (Render)**: pushes to `main` only; deploys those exact images to Render and waits until production reports the new commit

`main` is protected: changes go through a pull request, and checks 1-3 must pass before merging.

Production setup, rollback, and running the published images with `docker-compose.prod.yml` are described in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
