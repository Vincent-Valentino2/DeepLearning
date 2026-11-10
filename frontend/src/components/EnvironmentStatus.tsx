import { Activity, Database, GitCommitHorizontal, Globe, RefreshCw, Server, Tag } from 'lucide-react'
import type { ReactNode } from 'react'
import type { EnvironmentHealth, ProbeState } from '../hooks/useEnvironmentHealth'

const REPO_URL = 'https://github.com/Vincent-Valentino2/DeepLearning'
const WORKFLOW_FILE = 'ci-cd.yml'

const BUILD_COMMIT_SHA: string = import.meta.env.VITE_GIT_COMMIT_SHA || 'unknown'
const BUILD_RELEASE_ENV: string = import.meta.env.VITE_RELEASE_ENV || (import.meta.env.DEV ? 'development' : 'production')

const DOT: Record<ProbeState, string> = {
  checking: 'bg-amber-400 animate-pulse',
  up: 'bg-emerald-600',
  degraded: 'bg-amber-500',
  down: 'bg-rose-500',
}

const LABEL: Record<ProbeState, string> = {
  checking: 'checking',
  up: 'online',
  degraded: 'degraded',
  down: 'offline',
}

function shortSha(sha: string | undefined | null) {
  if (!sha || sha === 'unknown') return 'unknown'
  return sha.slice(0, 7)
}

function isRealSha(sha: string | undefined | null): sha is string {
  return !!sha && /^[0-9a-f]{7,40}$/i.test(sha)
}

function StatusPill({
  icon,
  name,
  state,
  detail,
  title,
}: {
  icon: ReactNode
  name: string
  state: ProbeState
  detail: string
  title: string
}) {
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-0.5 rounded border border-[#e5e2da] bg-white whitespace-nowrap"
      title={title}
      role="status"
      aria-label={`${name}: ${LABEL[state]}. ${detail}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${DOT[state]}`} />
      <span className="text-[#a8a29e]">{icon}</span>
      <span className="font-medium text-[#1c1917]">{name}</span>
      <span className="text-[#78716c]">{detail}</span>
    </div>
  )
}

function envBadgeClass(env: string) {
  const e = env.toLowerCase()
  if (e.startsWith('prod')) return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (e.startsWith('stag')) return 'border-amber-200 bg-amber-50 text-amber-800'
  return 'border-sky-200 bg-sky-50 text-sky-800'
}

/** Thin strip under the masthead showing live status of all three containers. */
export function EnvironmentStatusBar({ health }: { health: EnvironmentHealth }) {
  const { frontend, backend, database } = health
  const db = database.info

  const backendDetail =
    backend.state === 'up'
      ? `/api/health ${backend.latencyMs} ms`
      : backend.state === 'checking'
        ? '/api/health …'
        : `/api/health ${backend.error ?? 'unreachable'}`

  const dbName = db?.engine === 'sqlite' ? 'SQLite' : 'PostgreSQL'
  const dbDetail =
    database.state === 'checking'
      ? '…'
      : db?.connected
        ? db.engine === 'sqlite'
          ? 'fallback store'
          : `connected ${db.latency_ms} ms`
        : db
          ? 'connection failed'
          : 'unknown (API offline)'

  return (
    <div className="border-t border-[#e5e2da] bg-[#fcfbf9]">
      <div className="max-w-7xl mx-auto px-6 py-1.5 flex items-center gap-2 overflow-x-auto text-[11px] font-mono">
        <span className="flex items-center gap-1 text-[#78716c] uppercase tracking-wider text-[10px] mr-1 whitespace-nowrap">
          <Activity className="w-3 h-3" /> Env
        </span>
        <StatusPill
          icon={<Globe className="w-3 h-3" />}
          name="Frontend"
          state={frontend.state}
          detail={`${frontend.server} :${frontend.port}`}
          title={`Frontend (${frontend.server}) serving on port ${frontend.port}${frontend.latencyMs != null ? ` · ${frontend.latencyMs} ms` : ''}`}
        />
        <StatusPill
          icon={<Server className="w-3 h-3" />}
          name="Backend"
          state={backend.state}
          detail={backendDetail}
          title="FastAPI container, polled every 10 s via GET /api/health"
        />
        <StatusPill
          icon={<Database className="w-3 h-3" />}
          name={dbName}
          state={database.state}
          detail={dbDetail}
          title={
            db?.error
              ? `Database error: ${db.error}`
              : db?.engine === 'sqlite'
                ? 'DATABASE_URL not set: the backend is using its local SQLite fallback'
                : 'PostgreSQL container, checked with SELECT 1 on every health poll'
          }
        />
        <div className="ml-auto flex items-center gap-2 pl-2 whitespace-nowrap">
          <span className={`px-1.5 py-0.5 rounded border text-[10px] uppercase tracking-wider ${envBadgeClass(BUILD_RELEASE_ENV)}`}>
            {BUILD_RELEASE_ENV}
          </span>
          <button
            type="button"
            onClick={health.refresh}
            className="flex items-center gap-1 text-[#78716c] hover:text-[#1c1917] cursor-pointer"
            title={health.lastChecked ? `Last checked ${health.lastChecked.toLocaleTimeString()}. Click to re-check now.` : 'Check now'}
          >
            <RefreshCw className="w-3 h-3" />
            <span className="hidden sm:inline">{health.lastChecked ? health.lastChecked.toLocaleTimeString() : '…'}</span>
          </button>
        </div>
      </div>
    </div>
  )
}

function CommitLink({ sha }: { sha: string }) {
  if (!isRealSha(sha)) return <span>{shortSha(sha)}</span>
  return (
    <a href={`${REPO_URL}/commit/${sha}`} target="_blank" rel="noreferrer" className="underline decoration-dotted hover:text-[#1c1917]">
      {shortSha(sha)}
    </a>
  )
}

/** Footer line with deployed commit SHA, release tag, and the live CI badge. */
export function ReleaseFooterInfo({ health }: { health: EnvironmentHealth }) {
  const backendSha = health.backendRelease?.commit_sha
  const backendDiffers = backendSha && shortSha(backendSha) !== shortSha(BUILD_COMMIT_SHA)

  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 pt-2 text-[11px] font-mono text-[#a8a29e]">
      <span className="flex items-center gap-1" title="Commit the frontend bundle was built from">
        <GitCommitHorizontal className="w-3.5 h-3.5" />
        commit <CommitLink sha={BUILD_COMMIT_SHA} />
      </span>
      {backendDiffers && (
        <span className="flex items-center gap-1" title="Commit the backend container is running">
          &bull; api <CommitLink sha={backendSha} />
        </span>
      )}
      <span className="flex items-center gap-1" title="Release environment tag">
        <Tag className="w-3.5 h-3.5" />
        <span className={`px-1.5 py-0.5 rounded border uppercase tracking-wider text-[10px] ${envBadgeClass(BUILD_RELEASE_ENV)}`}>
          {BUILD_RELEASE_ENV}
        </span>
        {health.backendRelease?.version && <span>v{health.backendRelease.version}</span>}
      </span>
      <a href={`${REPO_URL}/actions/workflows/${WORKFLOW_FILE}`} target="_blank" rel="noreferrer" title="GitHub Actions CI/CD pipeline">
        <img
          src={`${REPO_URL}/actions/workflows/${WORKFLOW_FILE}/badge.svg?branch=main`}
          alt="CI/CD Pipeline status"
          className="h-5"
          loading="lazy"
        />
      </a>
    </div>
  )
}
