# Production deployment with containers (GHCR + Watchtower)

Production runs the three container images that CI built and tested. The server never
receives or builds source code: it pulls public images from the GitHub Container Registry (GHCR)
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
                                                     then all three :latest -> <sha> together
                                                        │
                                                        ├─> Watchtower on the server sees the new
                                                        │   :latest within a minute, pulls it and
                                                        │   recreates the containers (no runner needed)
                                                        │
                                                  5. (optional) Deploy to Production Server (self-hosted runner)
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

Each is tagged with the commit SHA (an immutable release) and `latest`, and built for both
`linux/amd64` and `linux/arm64`, so the same tag runs on Intel/AMD servers, ARM servers such as
Oracle Cloud Ampere, and Apple Silicon laptops.

## Automatic updates with Watchtower

This is the simplest way to keep a server current: every push to `main` that passes CI
publishes new images, and the server updates itself. No runner, SSH key or open port is needed.

No secrets are needed: the publish job logs in to GHCR with the workflow's own
`GITHUB_TOKEN`, and the three packages are **public**, so the server pulls them without logging in.
If you create a fork, make its packages public too (GitHub profile > Packages > package >
Package settings > Change visibility).

1. **Start the stack on the server once**, with the tag left at `latest`:
   ```bash
   curl -fsSLO https://raw.githubusercontent.com/Vincent-Valentino2/DeepLearning/main/docker-compose.prod.yml
   docker compose -f docker-compose.prod.yml up -d --wait
   ```
   Put `FRONTEND_PORT` and `POSTGRES_PASSWORD` in a `.env` file next to the compose file so
   later commands pick them up too.
2. **Push to `main`.** After CI passes and the publish job finishes, Watchtower notices the new
   `latest` (it checks every `WATCHTOWER_POLL_INTERVAL` seconds, default 60), pulls the images and
   recreates the frontend, backend and database containers one at a time. The database volume is
   kept. Watch it happen:
   ```bash
   docker compose -p tmdb-prod logs -f watchtower
   curl http://localhost:3000/api/health   # release.commit_sha changes to the new commit
   ```

How it fits together:

- CI pushes `:<sha>` for all three images first and only then moves `:latest`, so Watchtower never
  runs a new frontend against an old backend mid-publish.
- Watchtower only touches containers labelled `com.centurylinklabs.watchtower.enable=true` (the
  three app containers), not the development stack or anything else on the machine.
- The compose file uses `nickfedor/watchtower`, the maintained fork. The original
  `containrrr/watchtower` image is archived and fails on Docker Engine 29+ with
  "client version 1.25 is too old".
- A stack started with `TAG=<sha>` (the runner deploy or a rollback) is pinned; that tag never
  moves, so Watchtower leaves it alone. Use one mode per server: either Watchtower (`TAG` unset,
  `DEPLOY_SERVER_ENABLED` unset) or the runner deploy below.
- Private images: run `docker login` on the server and add
  `- ~/.docker/config.json:/config.json:ro` to the watchtower service's volumes.

## Why a self-hosted runner

The deploy job runs on a GitHub Actions runner installed on the server itself. The runner
only makes outbound connections to GitHub, so it works on a VPS and on a laptop without a
public IP, and no SSH keys or open ports are needed. The job fetches only
`docker-compose.prod.yml`, pulls the images for the commit, and restarts the stack.

## One-time server setup

Requirements: Docker with the Compose plugin (Docker Desktop on macOS/Windows), `curl`,
`python3`, and outbound internet access.

1. **Install the runner.** Repository > Settings > Actions > Runners > **New self-hosted runner**.
   Pick the server's OS and run the commands GitHub shows. When `config.sh` asks for labels,
   enter **`production`**.
   - Linux: run it as a service (`sudo ./svc.sh install && sudo ./svc.sh start`) and make sure the
     runner user can use Docker (`sudo usermod -aG docker <user>`, then log in again).
   - macOS laptop: start it with `./run.sh` in a terminal while Docker Desktop is running.
2. **Enable deployments.** Repository > Settings > Secrets and variables > Actions:

   | Kind | Name | Value |
   | --- | --- | --- |
   | Variable | `DEPLOY_SERVER_ENABLED` | `true` (the deploy job is skipped until this is set) |
   | Variable | `FRONTEND_PORT` | optional, host port of the app (default `3000`) |
   | Variable | `PRODUCTION_URL` | optional, link shown on the run, e.g. `http://<server-ip>:3000` |
   | Secret | `POSTGRES_PASSWORD` | optional, database password (default `deeplearning_secret`) |

3. **Protect the runner.** This repository is public. Under Settings > Actions > General >
   *Fork pull request workflows from outside collaborators*, choose **Require approval for all
   outside collaborators**, so nobody can run code on your server from a fork. The deploy job
   itself only runs for pushes to `main`.
4. **Deploy.** Merge to `main` (or re-run the latest workflow on `main`). Watch the
   **Deploy to Production Server** job; its summary lists the running containers and image tags.

If the database password is set after the first deploy, the existing volume keeps the old
password. Set it before the first deploy, or remove the volume (`docker volume rm tmdb-prod_pgdata`,
which deletes the data).

## Example: your own laptop as the server (macOS, Docker Desktop)

The simplest setup for a demo: the laptop runs the production stack, and GitHub Actions
deploys to it through a runner on the same laptop.

1. **Install Docker Desktop** and start it once (whale icon in the menu bar):
   - Apple Silicon: https://desktop.docker.com/mac/main/arm64/Docker.dmg
   - Intel: https://desktop.docker.com/mac/main/amd64/Docker.dmg
   - Check in a terminal: `docker compose version`
2. **Install the runner.** Repository > Settings > Actions > Runners > **New self-hosted runner** >
   **macOS** > **ARM64** (or x64 on Intel). Run the commands shown there in a new folder,
   e.g. `~/actions-runner`. When `./config.sh` asks:
   - runner group / name: press Enter (defaults are fine)
   - **additional labels: `production`**
   - work folder: press Enter
3. **Start the runner** whenever you want deployments to happen (keep the terminal open):
   ```bash
   cd ~/actions-runner && ./run.sh
   ```
   It prints `Listening for Jobs`. Docker Desktop must be running too.
4. **Repository settings:** `DEPLOY_SERVER_ENABLED=true` and `FRONTEND_PORT=8080`
   (8080 keeps the production stack apart from the development stack on 3000);
   optionally `PRODUCTION_URL=http://localhost:8080` and a `POSTGRES_PASSWORD` secret.
5. **Deploy:** merge to `main`, or Actions > the latest run on `main` > Re-run all jobs.
   The runner terminal shows the job; the app is then at http://localhost:8080.

Check the running release on the laptop:

```bash
docker compose -p tmdb-prod ps          # 3 containers, images ghcr.io/vincent-valentino2/...:<sha>
curl http://localhost:8080/api/health   # release.commit_sha = the deployed commit
```

## Example: free VPS on Oracle Cloud (Always Free, ARM)

Oracle Cloud's Always Free tier includes Ampere A1 (ARM) instances, enough for all three
containers. Sign-up needs card verification. Free limits changed in 2026; check Oracle's
Always Free page for the current numbers before creating the instance.

1. **Create the VM.** Oracle Cloud console > Compute > Instances > Create instance.
   - Image: **Canonical Ubuntu 24.04**.
   - Shape: **Ampere > VM.Standard.A1.Flex**, e.g. 1 OCPU / 6 GB (stay within the free allowance).
   - Networking: keep "Assign a public IPv4 address" on.
   - SSH keys: upload or download a key pair, then create the instance.
   - "Out of host capacity" is common for free ARM shapes: retry later or pick another
     availability domain.
2. **Open the app port** (80 gives a clean `http://<ip>` URL):
   - Instance > Subnet > Security list > Add ingress rule: source `0.0.0.0/0`, TCP, port `80`.
   - Oracle's Ubuntu images also filter with iptables. On the VM:
     ```bash
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
     sudo netfilter-persistent save
     ```
3. **Install Docker** on the VM (`ssh ubuntu@<ip>`):
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker ubuntu   # then log out and back in
   docker compose version
   ```
4. **Install the runner** as in step 1 of the one-time setup: choose **Linux** and **ARM64** on
   GitHub's "New self-hosted runner" page, enter the label `production`, then run it as a service:
   ```bash
   sudo ./svc.sh install ubuntu && sudo ./svc.sh start
   ```
5. **Repository settings:** `DEPLOY_SERVER_ENABLED=true`, `FRONTEND_PORT=80`,
   `PRODUCTION_URL=http://<ip>`, and a `POSTGRES_PASSWORD` secret.
6. **Deploy:** Actions > the latest run on `main` > Re-run all jobs, or merge a change.
   The app is then at `http://<ip>`.

Any other Linux VPS works the same way (for example cloud credits from student programs);
use the runner build that matches the server's CPU (x64 or ARM64).

## Checking a release

- On the server: `docker compose -p tmdb-prod ps` shows three containers running
  `ghcr.io/vincent-valentino2/...:<sha>` images.
- `http://<server>:3000/api/health` reports `release.commit_sha`, `model_loaded`, and the database.
- The app footer shows the commit the frontend image was built from.

## Rolling back

Every release stays on GHCR under its commit SHA. Re-run the workflow of an older green commit
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
