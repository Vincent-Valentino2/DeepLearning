import { useCallback, useEffect, useState } from 'react'

export type ProbeState = 'checking' | 'up' | 'degraded' | 'down'

export interface DatabaseHealth {
  engine: 'postgresql' | 'sqlite'
  configured: boolean
  connected: boolean
  latency_ms: number | null
  active_store: string | null
  error: string | null
}

export interface ReleaseInfo {
  commit_sha: string
  environment: string
  version: string
}

export interface EnvironmentHealth {
  frontend: { state: ProbeState; server: string; port: string; latencyMs: number | null }
  backend: { state: ProbeState; latencyMs: number | null; error: string | null }
  database: { state: ProbeState; info: DatabaseHealth | null }
  backendRelease: ReleaseInfo | null
  lastChecked: Date | null
  refresh: () => void
}

const POLL_INTERVAL_MS = 10_000
const REQUEST_TIMEOUT_MS = 5_000

function currentPort(): string {
  if (window.location.port) return window.location.port
  return window.location.protocol === 'https:' ? '443' : '80'
}

async function timedFetch(url: string, init?: RequestInit) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  const started = performance.now()
  try {
    const response = await fetch(url, { cache: 'no-store', ...init, signal: controller.signal })
    return { response, latencyMs: Math.round(performance.now() - started) }
  } finally {
    window.clearTimeout(timer)
  }
}

/** Polls the frontend server, `/api/health` and (through it) the database. */
export function useEnvironmentHealth(): EnvironmentHealth {
  const [frontend, setFrontend] = useState<EnvironmentHealth['frontend']>({
    state: 'checking',
    server: import.meta.env.DEV ? 'Vite dev server' : 'Nginx',
    port: currentPort(),
    latencyMs: null,
  })
  const [backend, setBackend] = useState<EnvironmentHealth['backend']>({ state: 'checking', latencyMs: null, error: null })
  const [database, setDatabase] = useState<EnvironmentHealth['database']>({ state: 'checking', info: null })
  const [backendRelease, setBackendRelease] = useState<ReleaseInfo | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const probe = useCallback(async () => {
    const frontendProbe = timedFetch('/', { method: 'HEAD' })
      .then(({ response, latencyMs }) =>
        setFrontend((prev) => ({ ...prev, state: response.ok ? 'up' : 'degraded', latencyMs })),
      )
      .catch(() => setFrontend((prev) => ({ ...prev, state: 'down', latencyMs: null })))

    const backendProbe = timedFetch('/api/health')
      .then(async ({ response, latencyMs }) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = await response.json()
        setBackend({ state: 'up', latencyMs, error: null })
        setBackendRelease(data.release ?? null)
        const db: DatabaseHealth | undefined = data.database
        if (!db) {
          setDatabase({ state: 'degraded', info: null })
        } else if (!db.connected) {
          setDatabase({ state: 'down', info: db })
        } else {
          // Connected, but on the SQLite fallback rather than the PostgreSQL container.
          setDatabase({ state: db.engine === 'postgresql' ? 'up' : 'degraded', info: db })
        }
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? (err.name === 'AbortError' ? 'timeout' : err.message) : 'unreachable'
        setBackend({ state: 'down', latencyMs: null, error: message })
        setDatabase({ state: 'down', info: null })
      })

    await Promise.allSettled([frontendProbe, backendProbe])
    setLastChecked(new Date())
  }, [])

  useEffect(() => {
    // Kick off the first probe from a timer so state updates never run inside the effect body.
    const initial = window.setTimeout(() => void probe(), 0)
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') void probe()
    }, POLL_INTERVAL_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') void probe()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [probe])

  return { frontend, backend, database, backendRelease, lastChecked, refresh: () => void probe() }
}
