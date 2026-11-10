# Database image: official PostgreSQL 16 with the application schema baked in.
# Published to GHCR like the frontend and backend, so a server needs no files from
# the repository: init.sql runs automatically the first time the data volume is created.
FROM postgres:16-alpine

COPY init.sql /docker-entrypoint-initdb.d/init.sql

# Defaults for the bundled app; override POSTGRES_PASSWORD on real servers.
ENV POSTGRES_USER=deeplearning \
    POSTGRES_DB=movierec_db

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
  CMD pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" || exit 1
