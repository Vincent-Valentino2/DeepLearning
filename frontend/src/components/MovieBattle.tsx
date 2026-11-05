import { useEffect, useState } from 'react'
import { ArrowLeftRight, Film, Search, Trophy } from 'lucide-react'
import { predictMovie, searchMovies } from '../api'
import type { MovieCatalogItem, PredictionResult } from '../types'

interface SideProps {
  label: string
  movie: MovieCatalogItem | null
  onSelect: (movie: MovieCatalogItem | null) => void
}

function MovieSelector({ label, movie, onSelect }: SideProps) {
  const [query, setQuery] = useState('')
  const [matches, setMatches] = useState<MovieCatalogItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!query.trim()) return
    const timer = window.setTimeout(async () => {
      setLoading(true)
      try { setMatches(await searchMovies(query)) } catch { setMatches([]) } finally { setLoading(false) }
    }, 220)
    return () => window.clearTimeout(timer)
  }, [query])

  return <div className="rounded-xl border border-[#e5e2da] bg-white p-4 space-y-3">
    <span className="text-[10px] font-mono uppercase tracking-widest text-[#78716c]">{label}</span>
    {movie ? <div className="flex gap-3 min-w-0">
      {movie.poster_url ? <img src={movie.poster_url} alt="" className="h-20 w-14 rounded object-cover border border-[#e5e2da]" /> : <div className="h-20 w-14 rounded bg-[#f0eee6] grid place-items-center"><Film className="w-4 h-4 text-[#78716c]" /></div>}
      <div className="min-w-0"><h3 className="font-serif font-bold text-base truncate">{movie.title}</h3><p className="text-[10px] font-mono text-[#78716c] mt-1">{movie.release_year ?? '—'} · {movie.runtime ? `${movie.runtime}m` : 'Runtime N/A'} · {(movie.original_language ?? '—').toUpperCase()}</p><p className="text-[10px] text-[#57534e] mt-2 line-clamp-2">{movie.genres?.join(', ') || 'Uncategorized'}</p><button type="button" onClick={() => onSelect(null)} className="mt-2 text-[10px] font-mono underline text-[#78716c] hover:text-[#1c1917]">Change film</button></div>
    </div> : <>
      <div className="relative"><Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-[#78716c]" /><input value={query} onChange={e => { setQuery(e.target.value); if (!e.target.value.trim()) setMatches([]) }} placeholder="Search TMDB catalog" className="w-full rounded-lg border border-[#d6d3d1] bg-[#fcfbf9] py-2 pl-9 pr-3 text-xs focus:outline-none focus:border-[#1c1917]" />{loading && <span className="absolute right-3 top-2.5 text-[10px] font-mono text-[#78716c]">Searching</span>}</div>
      {matches.length > 0 && <div className="max-h-48 overflow-y-auto divide-y divide-[#f0eee6] border border-[#e5e2da] rounded-lg">{matches.map(item => <button type="button" key={item.id ?? item.title} onClick={() => { onSelect(item); setQuery(''); setMatches([]) }} className="w-full flex gap-2 p-2 text-left hover:bg-[#f8f7f4]"><span className="font-bold text-xs truncate">{item.title}</span><span className="text-[10px] font-mono text-[#78716c] shrink-0">{item.release_year}</span></button>)}</div>}
      <div className="h-20 border border-dashed border-[#d6d3d1] rounded-lg grid place-items-center text-[11px] font-mono text-[#a8a29e]">Choose a film to enter the battle</div>
    </>}
  </div>
}

function Score({ movie, result, max }: { movie: MovieCatalogItem, result: PredictionResult, max: number }) {
  return <div className="space-y-2"><div className="flex justify-between text-xs"><span className="font-serif font-bold truncate pr-2">{movie.title}</span><strong className="font-mono">{(result.probability * 100).toFixed(1)}%</strong></div><div className="h-2 rounded-full bg-[#e5e2da] overflow-hidden"><div className="h-full bg-[#1c1917] rounded-full transition-all duration-700" style={{ width: `${Math.max(5, (result.probability / max) * 100)}%` }} /></div><p className="text-[10px] font-mono text-[#78716c]">{result.prediction} · {result.model_architecture}</p></div>
}

export function MovieBattle({ onPrediction }: { onPrediction?: () => void }) {
  const [left, setLeft] = useState<MovieCatalogItem | null>(null)
  const [right, setRight] = useState<MovieCatalogItem | null>(null)
  const [results, setResults] = useState<[PredictionResult, PredictionResult] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const compare = async () => { if (!left || !right) return; setLoading(true); setError(''); try { setResults(await Promise.all([predictMovie(left), predictMovie(right)])); onPrediction?.() } catch (e) { setResults(null); setError(e instanceof Error ? e.message : 'Comparison failed.') } finally { setLoading(false) } }
  const winner = results && left && right ? results[0].probability === results[1].probability ? null : results[0].probability > results[1].probability ? left.title : right.title : null
  const max = results ? Math.max(...results.map(result => result.probability), .01) : 1
  return <section className="bg-white border border-[#e5e2da] rounded-xl p-5 sm:p-6 shadow-xs space-y-5">
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3"><div><p className="text-[10px] font-mono uppercase tracking-widest text-[#78716c]">Head-to-Head</p><h2 className="font-serif font-bold text-xl">Movie Battle Mode</h2><p className="text-xs text-[#78716c] mt-1">Compare genuine MLP popularity probabilities; this model does not estimate revenue.</p></div><button type="button" disabled={!left || !right || loading} onClick={compare} className="inline-flex justify-center items-center gap-2 rounded-lg bg-[#1c1917] px-4 py-2.5 text-xs font-medium text-white disabled:opacity-40 hover:bg-[#2e2a27]"><ArrowLeftRight className="w-4 h-4" />{loading ? 'Running model…' : 'Compare films'}</button></div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4"><MovieSelector label="Challenger A" movie={left} onSelect={setLeft} /><MovieSelector label="Challenger B" movie={right} onSelect={setRight} /></div>
    {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</div>}
    {results && left && right && <div className="rounded-xl border border-[#e5e2da] bg-[#fcfbf9] p-4 space-y-4"><div className="flex items-center gap-2"><Trophy className="w-4 h-4 text-amber-600" /><span className="font-serif font-bold">{winner ? `${winner} leads the model forecast` : 'Even model forecast'}</span></div><Score movie={left} result={results[0]} max={max} /><Score movie={right} result={results[1]} max={max} /></div>}
  </section>
}
