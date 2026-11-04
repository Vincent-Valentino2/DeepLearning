export interface MovieCatalogItem {
  id?: number
  title: string
  original_title?: string
  release_year?: number
  runtime?: number
  genres?: string[]
  original_language?: string
  budget?: number
  tagline?: string
  overview?: string
  poster_path?: string
  poster_url?: string | null
  backdrop_url?: string | null
  vote_average?: number
}

export interface PredictionResult {
  title: string
  prediction: string
  is_popular: boolean
  probability: number
  threshold_percentile: string
  confidence_level: string
  model_architecture: string
  input_features: {
    genres: string[]
    release_year: number
    runtime: number
    original_language: string
    budget: number
  }
  feature_insights: string[]
  poster_url?: string | null
  tagline?: string | null
  overview?: string | null
}

export interface PredictionLog {
  id: number
  title: string
  probability: number
  prediction: string
  is_popular: boolean | number
  model_architecture: string
  release_year?: number
  runtime?: number
  budget?: number
  original_language?: string
  genres?: string
  poster_url?: string | null
  created_at: string
}
