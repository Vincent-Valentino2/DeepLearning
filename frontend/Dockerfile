# Multi-stage Dockerfile for React + Vite Frontend
# The build output is plain static files, so build on the runner's native platform
# even when producing arm64 images (much faster than emulating Node under QEMU).
FROM --platform=$BUILDPLATFORM node:22-alpine AS builder

WORKDIR /app

# Enable pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Install dependencies
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Release metadata baked into the bundle (shown in the UI footer)
ARG GIT_COMMIT_SHA=unknown
ARG RELEASE_ENV=production
ENV VITE_GIT_COMMIT_SHA=$GIT_COMMIT_SHA \
    VITE_RELEASE_ENV=$RELEASE_ENV

# Copy source and build
COPY . .
RUN pnpm run build

# Production stage using Nginx
FROM nginx:alpine

# Copy built assets to Nginx html directory
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config template: the image renders it with envsubst at start-up
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Defaults for docker compose; the cloud host overrides them at run time
ENV PORT=80 \
    BACKEND_URL=http://backend:8001

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
