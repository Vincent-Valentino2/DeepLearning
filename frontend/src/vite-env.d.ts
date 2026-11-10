/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Git commit the bundle was built from (Docker build arg or local `git rev-parse`). */
  readonly VITE_GIT_COMMIT_SHA?: string
  readonly VITE_FRONTEND_HOST?: string
  /** Release environment tag, e.g. development, staging, production. */
  readonly VITE_RELEASE_ENV?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
