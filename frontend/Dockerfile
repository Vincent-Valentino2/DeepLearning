# Multi-stage Dockerfile for React + Vite Frontend
FROM node:22-alpine AS builder

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

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
