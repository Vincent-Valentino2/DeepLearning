# Production deployment with containers (GHCR + self-hosted runner)

Production runs the three container images that CI built and tested. The server never
receives or builds source code: it pulls images from GitHub Container Registry (GHCR)
and starts them with `docker-compose.prod.yml`.

```text
push / PR ──> 1. Frontend Lint & Build Check ─┐
              2. Backend Syntax & Health ─────┼─> 3. Docker Multi-Container Build Verification
                                              │      (builds FE+BE+DB images, runs them, checks health)
                                              │
push to main only ────────────────────────────┴─> 4. Publish Container Images (GHCR)
                                                     ghcr.io/vincent-valentino2/deeplearning-frontend:<sha>
                                                     ghcr.io/vincent-valentino2/deeplearning-backend:<sha>
                                                     ghcr.io/vincent-valentino2/deeplearning-database:<sha>
                                                  5. Deploy to Production Server (self-hosted runner)
                                                     docker compose pull  (TAG=<sha>)
                                                     docker compose up -d --wait
                                                     smoke test: /api/health reports <sha>, DB connected
```

Pull requests run steps 1-3 only. `main` is protected, so an image reaches the server only
after review and green CI.

## The three images

| Image | Built from | Contains |
| --- | --- | --- |
| `deeplearning-frontend` | `frontend/Dockerfile` | React build served by Nginx; proxies `/api` to the backend |
| `deeplearning-backend` | `backend/Dockerfile` | FastAPI, the trained MLP model, the compact movie catalog |
| `deeplearning-database` | `database/Dockerfile` | PostgreSQL 16 with `init.sql` baked in |

Each is tagged with the commit SHA (an immutable release) and `latest`.

## Why a self-hosted runner

The deploy job runs on a GitHub Actions runner installed on the server itself. The runner
only makes outbound connections to GitHub, so it works on a VPS and on a laptop without a
public IP, and no SSH keys or open ports are needed. The job fetches only
`docker-compose.prod.yml`, pulls the images for the commit, and restarts the stack.

## One-time server setup

Requirements: Docker with the Compose plugin (Docker Desktop on macOS/Windows), `curl`,
`python3`, and outbound internet access.

1. **Make the images public** (once, after the first push to `main` publishes them):
   GitHub > profile > Packages > each `deeplearning-*` package > Package settings >
   Change visibility > Public. The server can then pull without a registry login.
2. **Install the runner.** Repository > Settings > Actions > Runners > **New self-hosted runner**.
   Pick the server's OS and run the commands GitHub shows. When `config.sh` asks for labels,
   enter **`production`**.
   - Linux: run it as a service (`sudo ./svc.sh install && sudo ./svc.sh start`) and make sure the
     runner user can use Docker (`sudo usermod -aG docker <user>`, then log in again).
   - macOS laptop: start it with `./run.sh` in a terminal while Docker Desktop is running.
3. **Enable deployments.** Repository > Settings > Secrets and variables > Actions:

   | Kind | Name | Value |
   | --- | --- | --- |
   | Variable | `DEPLOY_SERVER_ENABLED` | `true` (the deploy job is skipped until this is set) |
   | Variable | `FRONTEND_PORT` | optional, host port of the app (default `3000`) |
   | Variable | `PRODUCTION_URL` | optional, link shown on the run, e.g. `http://<server-ip>:3000` |
   | Secret | `POSTGRES_PASSWORD` | optional, database password (default `deeplearning_secret`) |

4. **Protect the runner.** This repository is public. Under Settings > Actions > General >
   *Fork pull request workflows from outside collaborators*, choose **Require approval for all
   outside collaborators**, so nobody can run code on your server from a fork. The deploy job
   itself only runs for pushes to `main`.
5. **Deploy.** Merge to `main` (or re-run the latest workflow on `main`). Watch the
   **Deploy to Production Server** job; its summary lists the running containers and image tags.

If the database password is set after the first deploy, the existing volume keeps the old
password. Set it before the first deploy, or remove the volume (`docker volume rm tmdb-prod_pgdata`,
which deletes the data).

## Checking a release

- On the server: `docker compose -p tmdb-prod ps` shows three containers running
  `ghcr.io/...:<sha>` images.
- `http://<server>:3000/api/health` reports `release.commit_sha`, `model_loaded`, and the database.
- The app footer shows the commit the frontend image was built from.

## Rolling back

Every release stays in GHCR under its commit SHA. Re-run the workflow of an older green commit
on `main` (Actions > run > Re-run all jobs): the deploy job pulls that commit's images and
restarts the stack. Manually on the server:

```bash
TAG=<older-sha> docker compose -f docker-compose.prod.yml up -d --wait
```

## Deploying by hand (no runner)

Any machine with Docker can run a release with only the compose file:

```bash
curl -fsSLO https://raw.githubusercontent.com/Vincent-Valentino2/DeepLearning/main/docker-compose.prod.yml
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --wait
```

## Notes

- Only the frontend publishes a port. The backend and database are reachable only on the
  stack's private network.
- The production stack uses the project name `tmdb-prod`, so it does not clash with the
  development stack (`docker compose up`) on the same machine; only the frontend port must differ
  (set `FRONTEND_PORT`).
- Movie search uses the compact catalog inside the backend image (27,627 films). The full index
  (`data/movies.db`) is used only in development, where `./data` is mounted.
