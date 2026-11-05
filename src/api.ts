import type { MovieCatalogItem, PredictionLog, PredictionResult } from './types'

export type PredictionPayload = Pick<
  MovieCatalogItem,
  'title' | 'genres' | 'release_year' | 'runtime' | 'original_language' | 'budget' | 'poster_url' | 'tagline' | 'overview'
>

export async function searchMovies(query: string, limit = 6): Promise<MovieCatalogItem[]> {
  const response = await fetch(`/api/movies/search?q=${encodeURIComponent(query)}&limit=${limit}`)
  if (!response.ok) throw new Error('Movie catalog search failed.')
  const data = await response.json()
  return data.results ?? []
}

export async function predictMovie(movie: MovieCatalogItem): Promise<PredictionResult> {
  const payload: PredictionPayload = {
    title: movie.title,
    genres: movie.genres?.length ? movie.genres : ['Drama'],
    release_year: movie.release_year ?? 2024,
    runtime: movie.runtime ?? 110,
    original_language: movie.original_language ?? 'en',
    budget: movie.budget ?? 0,
    poster_url: movie.poster_url ?? undefined,
    tagline: movie.tagline ?? undefined,
    overview: movie.overview ?? undefined,
  }
  const response = await fetch('/api/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(`Prediction failed (HTTP ${response.status}).`)
  return response.json()
}

export async function getPredictionHistory(): Promise<PredictionLog[]> {
  const response = await fetch('/api/predictions?limit=50')
  if (!response.ok) throw new Error('Prediction history is unavailable.')
  const data = await response.json()
  return data.predictions ?? []
}
