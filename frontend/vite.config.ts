import { execSync } from 'node:child_process'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Release metadata shown in the footer. Docker/CI pass these as build args;
// local `pnpm dev` / `pnpm build` fall back to the checkout's current commit.
function resolveCommitSha(): string {
  if (process.env.VITE_GIT_COMMIT_SHA) return process.env.VITE_GIT_COMMIT_SHA
  try {
    return execSync('git rev-parse HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return 'unknown'
  }
}

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  define: {
    'import.meta.env.VITE_GIT_COMMIT_SHA': JSON.stringify(resolveCommitSha()),
    'import.meta.env.VITE_RELEASE_ENV': JSON.stringify(
      process.env.VITE_RELEASE_ENV || (command === 'serve' ? 'development' : 'production'),
    ),
  },
  server: {
    port: 5174,
    host: true,
    proxy: {
      '/api': {
        // Override with API_PROXY_TARGET when the API runs on another port.
        target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
}))
