# Production deployment (Render) and CI/CD

Every push to `main` goes through this pipeline (`.github/workflows/ci-cd.yml`):

```text
push / PR ──> 1. Frontend Lint & Build Check ─┐
              2. Backend Syntax & Health ─────┼─> 3. Docker Multi-Container Build Verification
                                              │      (builds FE+BE, runs FE+BE+DB, checks health)
                                              │
push to main only ────────────────────────────┴─> 4. Publish Container Images (GHCR)
                                                     ghcr.io/vincent-valentino2/deeplearning-{frontend,backend}:<sha> + :latest
                                                  5. Deploy to Production (Render)
                                                     deploy hooks with the <sha> images, then smoke test
```

Pull requests run steps 1-3 only. `main` is protected, so code reaches production only after
review and green CI. Production runs the exact images CI built and tested; nothing is rebuilt on the host.

## Why Render and not Vercel

Vercel hosts static sites and serverless functions; it cannot run Docker containers or a PostgreSQL
container. This project must be deployed as containers, so the production host is Render, which runs
prebuilt container images as web services (Fly.io, Railway, or Koyeb work the same way: the pipeline
only needs a "deploy this image" hook).

| Container | Local (`docker compose`) | Production (Render) |
| --- | --- | --- |
| Frontend (Nginx + React build) | `movie_frontend`, port 3000 | `tmdb-frontend` web service |
| Backend (FastAPI + MLP model) | `movie_backend`, port 8001 | `tmdb-backend` web service |
| Database (PostgreSQL 16) | `movie_postgres_db` container | `tmdb-db` managed PostgreSQL 16 |

The images read their runtime settings from environment variables, so the same image runs in both places:
`PORT` (port to listen on; Render injects its own), `BACKEND_URL` (frontend: where Nginx proxies `/api`),
and `DATABASE_URL` (backend).

## One-time setup

Do these once, in order. Only the repository owner can do steps 2 and 4.

1. **Publish the images.** Merge the CD change into `main`. The run publishes both images to GHCR; the
   deploy job is skipped with a warning because Render is not configured yet.
2. **Make the images public.** GitHub > your profile > Packages > `deeplearning-backend` > Package
   settings > Change visibility > Public. Repeat for `deeplearning-frontend`. (Render pulls them anonymously.)
3. **Create the Render services.** Render dashboard > New > Blueprint > select this repository. Render
   reads `render.yaml` and creates `tmdb-backend`, `tmdb-frontend`, and `tmdb-db`. When asked for
   `BACKEND_URL`, enter the backend's public URL (normally `https://tmdb-backend.onrender.com`; if Render
   gave it a suffix, update `BACKEND_URL` on `tmdb-frontend` afterwards).
4. **Connect GitHub Actions to Render.** For each web service: Settings > Deploy Hook > copy the URL.
   Then GitHub repository > Settings > Secrets and variables > Actions:

   | Kind | Name | Value |
   | --- | --- | --- |
   | Secret | `RENDER_DEPLOY_HOOK_BACKEND` | deploy hook of `tmdb-backend` |
   | Secret | `RENDER_DEPLOY_HOOK_FRONTEND` | deploy hook of `tmdb-frontend` |
   | Variable | `BACKEND_URL` | e.g. `https://tmdb-backend.onrender.com` |
   | Variable | `PRODUCTION_URL` | e.g. `https://tmdb-frontend.onrender.com` |

5. **Deploy.** Push any commit to `main` (or re-run the latest workflow). The deploy job triggers both
   hooks and waits until production reports the new commit SHA.

## Checking a release

- GitHub > Actions > the run > **Deploy to Production (Render)**: the summary shows the deployed commit;
  the `production` environment on the repository page links to the live site.
- `https://<frontend>/api/health` returns `release.commit_sha`, `model_loaded`, and the database status.
- The app footer shows the commit the frontend was built from.

## Rolling back

Re-run the workflow of an older green commit on `main` (Actions > run > Re-run all jobs). It redeploys
that commit's images, which are still in GHCR under their SHA tag.

## Running the published images on any Docker host

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
TAG=<commit-sha> docker compose -f docker-compose.prod.yml up -d   # a specific release
```

## Free-tier limits

- Free web services sleep after 15 minutes without traffic; the first request then takes about a minute.
- The free PostgreSQL database expires after 30 days; recreate it from the Blueprint if needed.
- The movie-catalog search needs `data/movies.db`, which is too large for the image, so search returns
  no results in production. Prediction, comparison, history, analytics, and the watchlist work.
