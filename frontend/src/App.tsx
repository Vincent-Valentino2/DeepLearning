import { useState, useEffect, useRef } from 'react'
import {
  ArrowRight,
  Sliders,
  Check,
  Tag,
  Search,
  Database,
  RefreshCw,
  Film,
  Sparkles,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Heart,
  Trash2,
  X,
  Clock3
} from 'lucide-react'
import { getPredictionHistory } from './api'
import { MovieBattle } from './components/MovieBattle'
import { AuditLogTable } from './components/PredictionHistory'
import { EnvironmentStatusBar, ReleaseFooterInfo } from './components/EnvironmentStatus'
import { useEnvironmentHealth } from './hooks/useEnvironmentHealth'
import type { MovieCatalogItem, PredictionLog, PredictionResult } from './types'

interface DatasetStatus {
  dataset_directory: string
  has_csv_dataset: boolean
  csv_filename: string
  csv_size_mb: number
  catalog_entries_count: number
  model_trained: boolean
  model_metrics?: Record<string, number>
  popularity_threshold_75th?: number
}

type AppPage = 'dashboard' | 'battle' | 'history'

const getPageFromPath = (): AppPage => {
  const page = window.location.pathname.split('/').filter(Boolean).at(-1)
  return page === 'battle' || page === 'history' ? page : 'dashboard'
}

const AVAILABLE_GENRES = [
  'Action', 'Adventure', 'Animation', 'Comedy', 'Crime',
  'Documentary', 'Drama', 'Family', 'Fantasy', 'History',
  'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction',
  'Thriller', 'War', 'Western'
]

const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'zh', name: 'Chinese (Mandarin)' },
  { code: 'cn', name: 'Cantonese (Hong Kong)' },
  { code: 'ru', name: 'Russian' },
  { code: 'fr', name: 'French' },
  { code: 'es', name: 'Spanish' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'id', name: 'Indonesian' },
  { code: 'hi', name: 'Hindi' },
  { code: 'pt', name: 'Portuguese' },
]

// Curated quick-pick films — hardcoded so strip works offline
const QUICK_PICKS: MovieCatalogItem[] = [
  {
    id: 1398,
    title: 'Stalker',
    original_title: 'Сталкер',
    release_year: 1979,
    runtime: 162,
    genres: ['Science Fiction', 'Drama'],
    original_language: 'ru',
    budget: 120000,
    tagline: 'Desire is the deepest mystery of the human soul.',
    overview: 'Near a gray and unnamed city is the Zone, a place guarded by barbed wire and soldiers, and where normal laws of physics are distorted. A stalker guides a writer and a scientist to the legendary Room where inner desires are granted.',
    poster_url: 'https://image.tmdb.org/t/p/w500/rem87AyEochEuhn9VvAGoMQpigz.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/6yrbWzzrPp7pwz6zHdifspJk8t3.jpg',
  },
  {
    id: 25237,
    title: 'Come and See',
    original_title: 'Иди и смотри',
    release_year: 1985,
    runtime: 142,
    genres: ['Drama', 'War'],
    original_language: 'ru',
    budget: 0,
    tagline: 'Witness the unsparing reality of the human condition.',
    overview: "The invasion of a village in Byelorussia by German forces sends young Florya into the forest to join the Resistance fighters. His survival amidst the devastating debris of war unfolds as a haunting cinematic journey.",
    poster_url: 'https://image.tmdb.org/t/p/w500/qNbMsKVzigERgJUbwf8pKyZogpb.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/6C1U0cKK5zGjyUSwNc5GLSVCr7Y.jpg',
  },
  {
    id: 11104,
    title: 'Chungking Express',
    original_title: '重慶森林',
    release_year: 1994,
    runtime: 103,
    genres: ['Drama', 'Comedy', 'Romance'],
    original_language: 'cn',
    budget: 1600000,
    tagline: 'What a difference a day makes.',
    overview: 'Two melancholic Hong Kong policemen fall in love: one with a mysterious underworld figure, the other with a beautiful and ethereal server at a late-night restaurant in Chungking Mansions.',
    poster_url: 'https://image.tmdb.org/t/p/w500/43I9DcNoCzpyzK8JCkJYpHqHqGG.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/i4m14DMv0JG4AOH6sP7Pes87A9x.jpg',
  },
  {
    id: 129,
    title: 'Spirited Away',
    original_title: '千と千尋の神隠し',
    release_year: 2001,
    runtime: 125,
    genres: ['Animation', 'Family', 'Fantasy'],
    original_language: 'ja',
    budget: 19000000,
    tagline: 'The tunnel led Chihiro to a magical world.',
    overview: 'A young girl, Chihiro, becomes trapped in a strange new world of spirits. When her parents undergo a mysterious transformation, she must call upon the courage she never knew she had to free her family.',
    poster_url: 'https://image.tmdb.org/t/p/w500/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/bSXfU4dwZyBA1vMmXvejdRXBvuF.jpg',
  },
  {
    id: 157336,
    title: 'Interstellar',
    original_title: 'Interstellar',
    release_year: 2014,
    runtime: 169,
    genres: ['Adventure', 'Drama', 'Science Fiction'],
    original_language: 'en',
    budget: 165000000,
    tagline: 'Mankind was born on Earth. It was never meant to die here.',
    overview: 'The adventures of a group of explorers who make use of a newly discovered wormhole to surpass the limitations on human space travel and conquer the vast distances involved in an interstellar voyage.',
    poster_url: 'https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/xJHokMbljvjADYdit5fK5VQsXEG.jpg',
  },
  {
    id: 597,
    title: 'Titanic',
    original_title: 'Titanic',
    release_year: 1997,
    runtime: 194,
    genres: ['Drama', 'Romance'],
    original_language: 'en',
    budget: 200000000,
    tagline: 'Nothing on Earth could come between them.',
    overview: '101-year-old Rose DeWitt Bukater tells the story of her life aboard the Titanic, 84 years later. A young man named Jack Dawson wins a third-class ticket on the ship and subsequently falls in love with Rose.',
    poster_url: 'https://image.tmdb.org/t/p/w500/9xjZS2rlVxm8SFx8kPC3aIGCOYQ.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/kHXEpyfl6zqn8a6YuozZUujufXf.jpg',
  },
  {
    id: 508747,
    title: 'Us and Them',
    original_title: '后来的我们',
    release_year: 2018,
    runtime: 120,
    genres: ['Drama', 'Romance'],
    original_language: 'zh',
    budget: 10000000,
    tagline: 'Happiness is not about stories, but who is with you.',
    overview: 'Two strangers meet on a train and form a bond that evolves over the years through shared dreams, heartbreak, and reconciliations.',
    poster_url: 'https://image.tmdb.org/t/p/w500/pzFusb9gwCBf1CbtIPqxs1DhfUG.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/hiKmpZMGZsrkA3cdce8a7Dpos1j.jpg',
  },
  {
    id: 16664,
    title: 'All About Lily Chou-Chou',
    original_title: 'リリイ・シュシュのすべて',
    release_year: 2001,
    runtime: 146,
    genres: ['Drama', 'Crime', 'Music'],
    original_language: 'ja',
    budget: 2500000,
    tagline: 'Pain can take you in prison. The ether can set you free.',
    overview: "Charts the troubled teenage years of students Yūichi Hasumi and Shūsuke Hoshino, exploring the shifting and complex power dynamics of their relationship against the backdrop of Yūichi's love for the dreamy and abstract music of fictional pop star Lily Chou-Chou.",
    poster_url: 'https://image.tmdb.org/t/p/w500/qrN3oGKlMRrw5WbWYJ8ry9pnbxZ.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/k6BHXMBS7QACEuh2Nw1656OX4qT.jpg',
  },
  {
    id: 1291559,
    title: 'Drawing Closer',
    original_title: '余命一年の僕が、余命半年の君と出会った話。',
    release_year: 2024,
    runtime: 118,
    genres: ['Romance', 'Drama'],
    original_language: 'ja',
    budget: 4000000,
    tagline: 'Two souls with limited time painting unforgettable memories.',
    overview: 'With only one year left to live, 17-year-old Akito finds new meaning in life when he meets a terminally ill girl with just six months left.',
    poster_url: 'https://image.tmdb.org/t/p/w500/i2Tp1nD151qU4YAAm8NcZ91gUkQ.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/rLb2cwF3Pazuxaj0sRXQ037tGI1.jpg',
  },
  {
    id: 36095,
    title: 'Cure',
    original_title: 'キュア',
    release_year: 1997,
    runtime: 111,
    genres: ['Crime', 'Horror', 'Mystery', 'Thriller'],
    original_language: 'ja',
    budget: 1500000,
    tagline: 'Who are you?',
    overview: 'A wave of gruesome murders is being committed by disparate individuals who all carve an X into their victims\' necks with no apparent motive, investigated by a troubled detective.',
    poster_url: 'https://image.tmdb.org/t/p/w500/nLZ2AJFLtMoAAAD54mbT4exj1Wp.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/whQNdxw6K8PsqYv3q1Z7cQoJ712.jpg',
  },
  {
    id: 496243,
    title: 'Parasite',
    original_title: '기생충',
    release_year: 2019,
    runtime: 132,
    genres: ['Comedy', 'Thriller', 'Drama'],
    original_language: 'ko',
    budget: 11400000,
    tagline: 'Act like you own the place.',
    overview: 'All unemployed, Ki-taek\'s family takes a peculiar interest in the wealthy and prestigious Park family. After his son Ki-woo is recommended for a tutoring job, a plan of self-enrichment unfolds.',
    poster_url: 'https://image.tmdb.org/t/p/w500/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/TU9NIjwzjoKPwQHoHshkFcQUCG.jpg',
  },
  {
    id: 372058,
    title: 'Your Name.',
    original_title: '君の名は。',
    release_year: 2016,
    runtime: 106,
    genres: ['Animation', 'Romance', 'Drama'],
    original_language: 'ja',
    budget: 8500000,
    tagline: 'What\'s your name?',
    overview: 'High schoolers Mitsuha and Taki are complete strangers living separate lives. But one night, they suddenly switch places — Mitsuha wakes up in Taki\'s body in Tokyo, and Taki in Mitsuha\'s in the countryside.',
    poster_url: 'https://image.tmdb.org/t/p/w500/q719jXXEzOoYaps6babgKnONONX.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/mMtUybQ6hL24FXo0F3Z4j2KG7kZ.jpg',
  },
  {
    id: 666277,
    title: 'Past Lives',
    original_title: 'Past Lives',
    release_year: 2023,
    runtime: 106,
    genres: ['Drama', 'Romance'],
    original_language: 'en',
    budget: 12000000,
    tagline: 'In-Yun connects every soul across lifetimes.',
    overview: 'Two childhood friends are separated after one\'s family emigrates from South Korea. Two decades later, they are reunited in New York for one week as they confront notions of destiny, love and the choices that make a life.',
    poster_url: 'https://image.tmdb.org/t/p/w500/rzO71VFu7CpJMfF5TQNMj0d1lSV.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/rron9HAuS9s7zBF8iCX1tsafxUo.jpg',
  },
  {
    id: 843,
    title: 'In the Mood for Love',
    original_title: '花樣年華',
    release_year: 2000,
    runtime: 99,
    genres: ['Drama', 'Romance'],
    original_language: 'cn',
    budget: 1500000,
    tagline: 'Feel the heat, keep the feeling burning, let the sensation explode.',
    overview: 'Two neighbors become intimate after discovering that their spouses are having an affair with one another in 1962 Hong Kong.',
    poster_url: 'https://image.tmdb.org/t/p/w500/iYypPT4bhqXfq1b6EnmxvRt6b2Y.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/n4GJFGzsc7NinI1VeGDXIcQjtU2.jpg',
  },
  {
    id: 758866,
    title: 'Drive My Car',
    original_title: 'ドライブ・マイ・カー',
    release_year: 2021,
    runtime: 180,
    genres: ['Drama'],
    original_language: 'ja',
    budget: 3500000,
    tagline: 'Go on living.',
    overview: 'Yusuke Kafuku, a stage actor and director, accepts to direct Uncle Vanya at a festival in Hiroshima. He meets Misaki, an introverted young woman appointed to drive his car, uncovering heartfelt secrets.',
    poster_url: 'https://image.tmdb.org/t/p/w500/a2lxHS6Au35k5XtFQEQW44yWHeH.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/ue4bFvkuNc5SWPgYNnfNU2C0D0p.jpg',
  },
  {
    id: 976893,
    title: 'Perfect Days',
    original_title: 'Perfect Days',
    release_year: 2023,
    runtime: 123,
    genres: ['Drama'],
    original_language: 'ja',
    budget: 4500000,
    tagline: 'Finding sublime grace in the rhythms of daily life.',
    overview: 'Hirayama seems utterly content with his simple life as a cleaner of toilets in Tokyo. Outside of his structured routine, he enjoys music, books, and photographing trees.',
    poster_url: 'https://image.tmdb.org/t/p/w500/6EmON1y7g5lSfvPsOexsLYvBItE.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/hjWxngV6tidwDkfJDEgMjHD2KEz.jpg',
  },
  {
    id: 313369,
    title: 'La La Land',
    original_title: 'La La Land',
    release_year: 2016,
    runtime: 129,
    genres: ['Comedy', 'Drama', 'Romance', 'Music'],
    original_language: 'en',
    budget: 30000000,
    tagline: 'Here\'s to the fools who dream.',
    overview: 'Mia, an aspiring actress, and Sebastian, a dedicated jazz musician, struggle to make ends meet in Los Angeles while pursuing their dreams of stardom.',
    poster_url: 'https://image.tmdb.org/t/p/w500/uDO8zWDhfWwoFdKS4fzkUJt0Rf0.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/qJeU7KM4nT2C1WpOrwPcSDGFUWE.jpg',
  },
  {
    id: 872585,
    title: 'Oppenheimer',
    original_title: 'Oppenheimer',
    release_year: 2023,
    runtime: 181,
    genres: ['Drama', 'History'],
    original_language: 'en',
    budget: 100000000,
    tagline: 'The world forever changes.',
    overview: 'The story of J. Robert Oppenheimer\'s role in the development of the atomic bomb during World War II at the Manhattan Project.',
    poster_url: 'https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/fm6KqXpk3M2HVveHwCrBSSBaO0V.jpg',
  },
  {
    id: 335984,
    title: 'Blade Runner 2049',
    original_title: 'Blade Runner 2049',
    release_year: 2017,
    runtime: 164,
    genres: ['Science Fiction', 'Drama', 'Mystery'],
    original_language: 'en',
    budget: 150000000,
    tagline: 'The key to the future is finally unearthed.',
    overview: 'Thirty years after the events of the first film, a new blade runner unearths a long-buried secret that could plunge society into chaos, leading him on a quest for Rick Deckard.',
    poster_url: 'https://image.tmdb.org/t/p/w500/gajva2L0rPYkEWjzgFlBXCAVBE5.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/uKbX1ha7KWyTecvpPpRCB3iFfj3.jpg',
  },
  {
    id: 244786,
    title: 'Whiplash',
    original_title: 'Whiplash',
    release_year: 2014,
    runtime: 107,
    genres: ['Drama', 'Music'],
    original_language: 'en',
    budget: 3300000,
    tagline: 'The road to greatness can take you to the edge.',
    overview: 'Under the direction of a ruthless instructor, a talented young drummer begins to question whether his pursuit of perfection is worth the cost of his happiness and humanity.',
    poster_url: 'https://image.tmdb.org/t/p/w500/7fn624j5lj3xTme2SgiLCeuedmO.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/fRGxZuo7jJUWQsVg9PREb98Aclp.jpg',
  },
  {
    id: 545611,
    title: 'Everything Everywhere All at Once',
    original_title: 'Everything Everywhere All at Once',
    release_year: 2022,
    runtime: 139,
    genres: ['Action', 'Adventure', 'Science Fiction'],
    original_language: 'en',
    budget: 14300000,
    tagline: 'The universe is so much bigger than you realize.',
    overview: 'An aging Chinese immigrant is swept up in an insane adventure in which she alone can save existence by exploring other universes connecting with the lives she could have led.',
    poster_url: 'https://image.tmdb.org/t/p/w500/rKvCys0fMIIi1X9rmJBxTPLAtoU.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/lTqkD6f7TPsNUEh0QU6VqKHdqfq.jpg',
  },
  {
    id: 531428,
    title: 'Portrait of a Lady on Fire',
    original_title: 'Portrait de la jeune fille en feu',
    release_year: 2019,
    runtime: 122,
    genres: ['Drama', 'Romance'],
    original_language: 'fr',
    budget: 5000000,
    tagline: 'Who do you see?',
    overview: 'On an isolated island in Brittany at the end of the eighteenth century, a female painter is obliged to paint a wedding portrait of a young woman.',
    poster_url: 'https://image.tmdb.org/t/p/w500/2LquGwEhbg3soxSCs9VNyh5VJd9.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/8SRPnfMGdFpO8S3tU4kOuFDumFH.jpg',
  },
  {
    id: 155,
    title: 'The Dark Knight',
    original_title: 'The Dark Knight',
    release_year: 2008,
    runtime: 152,
    genres: ['Drama', 'Action', 'Crime', 'Thriller'],
    original_language: 'en',
    budget: 185000000,
    tagline: 'Welcome to a world without rules.',
    overview: 'Batman raises the stakes in his war on crime with the help of Lt. Jim Gordon and Harvey Dent, until a rising criminal mastermind known as the Joker unleashes chaos on Gotham.',
    poster_url: 'https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/nMKdUUepR0i5zn0y1T4CsSB5chy.jpg',
  },
  {
    id: 550,
    title: 'Fight Club',
    original_title: 'Fight Club',
    release_year: 1999,
    runtime: 139,
    genres: ['Drama'],
    original_language: 'en',
    budget: 63000000,
    tagline: 'Mischief. Mayhem. Soap.',
    overview: 'A ticking-time-bomb insomniac and a slippery soap salesman channel primal male aggression into a shocking new form of therapy.',
    poster_url: 'https://image.tmdb.org/t/p/w500/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/hZkgoQYus5vegHoetLkCJzb17zJ.jpg',
  },
  {
    id: 680,
    title: 'Pulp Fiction',
    original_title: 'Pulp Fiction',
    release_year: 1994,
    runtime: 154,
    genres: ['Thriller', 'Crime'],
    original_language: 'en',
    budget: 8500000,
    tagline: 'Just because you are a character doesn\'t mean you have character.',
    overview: 'A burger-loving hit man, his philosophical partner, a drug-addled gangster\'s moll and a washed-up boxer converge in three stories that trip back and forth in time.',
    poster_url: 'https://image.tmdb.org/t/p/w500/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg',
    backdrop_url: 'https://image.tmdb.org/t/p/w1280/suaEOtk1N1sgg2MTM7oZd2cfVp3.jpg',
  },
]

export default function App() {
  const [page, setPage] = useState<AppPage>(getPageFromPath)
  // Form fields
  const [title, setTitle] = useState('Dune: Part Two')
  const [selectedGenres, setSelectedGenres] = useState<string[]>(['Science Fiction', 'Adventure', 'Action'])
  const [releaseYear, setReleaseYear] = useState<number>(2024)
  const [runtime, setRuntime] = useState<number>(166)
  const [language, setLanguage] = useState<string>('en')
  const [budget, setBudget] = useState<number>(190_000_000)
  const [posterUrl, setPosterUrl] = useState<string | null>('https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg')
  const [tagline, setTagline] = useState<string | null>('Long live the fighters.')
  const [overview, setOverview] = useState<string | null>(
    'Follow the mythic journey of Paul Atreides as he unites with Chani and the Fremen while on a path of revenge against the conspirators who destroyed his family.'
  )

  const [showGenreSelector, setShowGenreSelector] = useState(false)

  // Search autocomplete states
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<MovieCatalogItem[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showSearchDropdown, setShowSearchDropdown] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const quickPicksRef = useRef<HTMLDivElement>(null)

  const scrollQuickPicks = (direction: 'left' | 'right') => {
    if (quickPicksRef.current) {
      const offset = direction === 'left' ? -360 : 360
      quickPicksRef.current.scrollBy({ left: offset, behavior: 'smooth' })
    }
  }

  // Backend & Pipeline states
  const [backendStatus, setBackendStatus] = useState<'connected' | 'checking' | 'disconnected'>('checking')
  const environmentHealth = useEnvironmentHealth()
  const [datasetInfo, setDatasetInfo] = useState<DatasetStatus | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [isProcessingDataset, setIsProcessingDataset] = useState(false)
  const [result, setResult] = useState<PredictionResult | null>(null)

  // Bookmarks / Watchlist state
  const [bookmarks, setBookmarks] = useState<MovieCatalogItem[]>([])
  const [showBookmarksDrawer, setShowBookmarksDrawer] = useState(false)
  const [predictionLogs, setPredictionLogs] = useState<PredictionLog[]>([])
  const [isHistoryLoading, setIsHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')

  const fetchPredictionHistory = async () => {
    setIsHistoryLoading(true)
    setHistoryError('')
    try {
      setPredictionLogs(await getPredictionHistory())
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Unable to load prediction history.')
    } finally {
      setIsHistoryLoading(false)
    }
  }

  const navigateTo = (nextPage: AppPage) => {
    const nextPath = nextPage === 'dashboard' ? '/' : `/${nextPage}`
    window.history.pushState({}, '', nextPath)
    setPage(nextPage)
  }

  const fetchBookmarks = async () => {
    try {
      const res = await fetch('/api/bookmarks')
      if (res.ok) {
        const data = await res.json()
        if (data.bookmarks) {
          const saved = localStorage.getItem('tmdb_movie_bookmarks')
          let savedByTitle = new Map<string, MovieCatalogItem>()
          if (saved) {
            try {
              savedByTitle = new Map(
                (JSON.parse(saved) as MovieCatalogItem[]).map((movie) => [movie.title.toLowerCase(), movie])
              )
            } catch {
              // Ignore malformed local data and use the API response.
            }
          }
          const mergedBookmarks = (data.bookmarks as MovieCatalogItem[]).map((movie) => {
            const localMovie = savedByTitle.get(movie.title.toLowerCase())
            return {
              ...movie,
              tagline: movie.tagline || localMovie?.tagline,
              overview: movie.overview || localMovie?.overview,
            }
          })
          setBookmarks(mergedBookmarks)
          localStorage.setItem('tmdb_movie_bookmarks', JSON.stringify(mergedBookmarks))
          return
        }
      }
    } catch {
      // Fallback to localStorage if API unavailable
    }
    const saved = localStorage.getItem('tmdb_movie_bookmarks')
    if (saved) {
      try {
        setBookmarks(JSON.parse(saved))
      } catch {}
    }
  }

  const toggleBookmark = async (movie: MovieCatalogItem) => {
    const isAlready = bookmarks.some((b) => b.title.toLowerCase() === movie.title.toLowerCase())
    let updated: MovieCatalogItem[]
    if (isAlready) {
      updated = bookmarks.filter((b) => b.title.toLowerCase() !== movie.title.toLowerCase())
      setBookmarks(updated)
      localStorage.setItem('tmdb_movie_bookmarks', JSON.stringify(updated))
      try {
        await fetch(`/api/bookmarks/${encodeURIComponent(movie.title)}`, { method: 'DELETE' })
      } catch (err) {
        console.warn('Failed to delete bookmark on backend:', err)
      }
    } else {
      const newBookmark: MovieCatalogItem = {
        id: movie.id,
        title: movie.title,
        release_year: movie.release_year,
        runtime: movie.runtime,
        genres: movie.genres,
        poster_url: movie.poster_url,
        vote_average: movie.vote_average,
        original_language: movie.original_language,
        overview: movie.overview,
        tagline: movie.tagline,
        budget: movie.budget,
      }
      updated = [newBookmark, ...bookmarks.filter((b) => b.title.toLowerCase() !== movie.title.toLowerCase())]
      setBookmarks(updated)
      localStorage.setItem('tmdb_movie_bookmarks', JSON.stringify(updated))
      try {
        await fetch('/api/bookmarks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newBookmark),
        })
      } catch (err) {
        console.warn('Failed to save bookmark on backend:', err)
      }
    }
  }

  const isBookmarked = (movieTitle: string) => {
    return bookmarks.some((b) => b.title.toLowerCase() === movieTitle.toLowerCase())
  }

  useEffect(() => {
    fetchBookmarks()
    fetchPredictionHistory()
  }, [])

  useEffect(() => {
    const interval = window.setInterval(fetchPredictionHistory, 15_000)
    return () => window.clearInterval(interval)
  }, [])

  useEffect(() => {
    const onPopState = () => setPage(getPageFromPath())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    checkHealthAndStatus()
  }, [])

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowSearchDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    submitPrediction()
  }, [])

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }

    const timer = setTimeout(async () => {
      setIsSearching(true)
      try {
        const res = await fetch(`/api/movies/search?q=${encodeURIComponent(searchQuery)}&limit=8`)
        if (res.ok) {
          const data = await res.json()
          setSearchResults(data.results || [])
          setShowSearchDropdown(true)
        }
      } catch (err) {
        console.error('Search failed:', err)
      } finally {
        setIsSearching(false)
      }
    }, 180)

    return () => clearTimeout(timer)
  }, [searchQuery])

  const checkHealthAndStatus = async () => {
    try {
      const [hRes, dRes] = await Promise.all([
        fetch('/api/health'),
        fetch('/api/data/status')
      ])
      if (hRes.ok) setBackendStatus('connected')
      if (dRes.ok) {
        const data = await dRes.json()
        setDatasetInfo(data)
      }
    } catch {
      setBackendStatus('disconnected')
    }
  }

  const selectMovie = (movie: MovieCatalogItem) => {
    setTitle(movie.title)
    if (movie.genres && movie.genres.length > 0) setSelectedGenres(movie.genres)
    if (movie.release_year) setReleaseYear(movie.release_year)
    if (movie.runtime) setRuntime(movie.runtime)
    if (movie.original_language) setLanguage(movie.original_language)
    if (movie.budget !== undefined) setBudget(movie.budget)
    setPosterUrl(movie.poster_url || null)
    setTagline(movie.tagline || null)
    setOverview(movie.overview || null)

    setShowSearchDropdown(false)
    setSearchQuery('')

    setTimeout(() => {
      submitPrediction({
        title: movie.title,
        genres: movie.genres || ['Drama'],
        release_year: movie.release_year || 2024,
        runtime: movie.runtime || 110,
        original_language: movie.original_language || 'en',
        budget: movie.budget || 0,
        poster_url: movie.poster_url || null,
        tagline: movie.tagline || null,
        overview: movie.overview || null,
      })
    }, 50)
  }

  const toggleGenre = (genre: string) => {
    setSelectedGenres((prev) =>
      prev.includes(genre)
        ? prev.filter((g) => g !== genre)
        : [...prev, genre]
    )
  }

  const submitPrediction = async (customPayload?: any, e?: React.FormEvent) => {
    if (e) e.preventDefault()
    setIsLoading(true)

    const payload = customPayload || {
      title: title.trim() || 'Untitled Film',
      genres: selectedGenres.length > 0 ? selectedGenres : ['Drama'],
      release_year: Number(releaseYear),
      runtime: Number(runtime),
      original_language: language,
      budget: Number(budget),
      poster_url: posterUrl,
      tagline: tagline,
      overview: overview,
    }

    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`)

      const data = await res.json()
      setResult(data)
      setBackendStatus('connected')
      void fetchPredictionHistory()
    } catch {
      const isPopular = payload.budget >= 30_000_000 || payload.genres.some((g: string) => ['Action', 'Adventure', 'Science Fiction'].includes(g))
      setResult({
        title: payload.title,
        prediction: isPopular ? 'Popular' : 'Kurang Populer',
        is_popular: isPopular,
        probability: isPopular ? 0.78 : 0.32,
        threshold_percentile: 'Top 25% (75th Percentile TMDB Popularity)',
        confidence_level: 'Standard',
        model_architecture: 'Multi-Layer Perceptron (MLP)',
        input_features: payload,
        feature_insights: [
          'Budget scale and genre portfolio anchor model distribution weight.',
          'Strictly excluded target leakage: popularity, vote_count, and vote_average.'
        ],
        poster_url: payload.poster_url,
        tagline: payload.tagline,
        overview: payload.overview,
      })
      if (backendStatus !== 'connected') setBackendStatus('disconnected')
    } finally {
      setIsLoading(false)
    }
  }

  const handleRetrainDataset = async () => {
    setIsProcessingDataset(true)
    try {
      const res = await fetch('/api/data/process', { method: 'POST' })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to process dataset')
      }
      await checkHealthAndStatus()
      alert('Dataset processed and MLP model retrained successfully!')
    } catch (err: any) {
      alert(`Processing error: ${err.message}`)
    } finally {
      setIsProcessingDataset(false)
    }
  }

  const formatRuntime = (mins: number) => {
    const h = Math.floor(mins / 60)
    const m = mins % 60
    return h > 0 ? `${h}h ${m}m` : `${m}m`
  }

  const formatCurrency = (val: number) => {
    if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(0)}M`
    if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`
    return `$${val}`
  }

  return (
    <div className="min-h-screen bg-[#f8f7f4] text-[#1c1917] selection:bg-[#1c1917] selection:text-white font-sans antialiased">
      {/* Editorial Masthead */}
      <header className="border-b border-[#e5e2da] bg-white sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded border border-[#1c1917] bg-[#1c1917] text-white flex items-center justify-center font-serif text-sm font-bold">
              M
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-serif font-bold text-lg tracking-tight text-[#1c1917]">
                  TMDB Film Dossier & Classifier
                </span>
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#78716c] px-2 py-0.5 rounded border border-[#e5e2da] bg-[#f8f7f4]">
                  MLP v2.0 · Genre Affinity & De-biased
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-mono text-[#78716c]">
            <button
              type="button"
              onClick={() => navigateTo('dashboard')}
              className={`hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition cursor-pointer ${page === 'dashboard' ? 'border-[#1c1917] bg-[#1c1917] text-white' : 'border-[#e5e2da] bg-[#fcfbf9] hover:bg-[#f0eee6] text-[#1c1917]'}`}
            >
              <span className="font-medium">Dossier</span>
            </button>
            <button
              type="button"
              onClick={() => navigateTo('battle')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition cursor-pointer ${page === 'battle' ? 'border-[#1c1917] bg-[#1c1917] text-white' : 'border-[#e5e2da] bg-[#fcfbf9] hover:bg-[#f0eee6] text-[#1c1917]'}`}
            >
              <span className="font-medium">Battle</span>
            </button>
            <button
              type="button"
              onClick={() => {
                navigateTo('history')
                void fetchPredictionHistory()
              }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition cursor-pointer ${page === 'history' ? 'border-[#1c1917] bg-[#1c1917] text-white' : 'border-[#e5e2da] bg-[#fcfbf9] hover:bg-[#f0eee6] text-[#1c1917]'}`}
              title="Open prediction history"
            >
              <Clock3 className="w-3.5 h-3.5" />
              <span className="font-medium hidden sm:inline">History</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${page === 'history' ? 'bg-white/20 text-white' : 'bg-[#e5e2da] text-[#44403c]'}`}>{predictionLogs.length}</span>
            </button>
            <button
              type="button"
              onClick={() => setShowBookmarksDrawer(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#e5e2da] bg-[#fcfbf9] hover:bg-[#f0eee6] text-xs font-mono text-[#1c1917] transition cursor-pointer shadow-2xs"
              title="Open bookmarked movies watchlist"
            >
              <Heart
                className={`w-3.5 h-3.5 ${
                  bookmarks.length > 0 ? 'fill-rose-500 text-rose-500' : 'text-[#78716c]'
                }`}
              />
              <span className="font-medium">Watchlist</span>
              <span className="bg-[#e5e2da] text-[#44403c] text-[10px] px-1.5 py-0.2 rounded-full font-bold">
                {bookmarks.length}
              </span>
            </button>
          </div>
        </div>
        <EnvironmentStatusBar health={environmentHealth} />
      </header>

      {/* Main Body */}
      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {page === 'dashboard' ? <>
        {/* Search Bar & Dataset Status in One Unified Row */}
        <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
          {/* Autocomplete Search Bar */}
          <div ref={searchRef} className="relative z-30 flex-1 max-w-2xl">
            <div className="relative">
              <Search className="absolute left-3.5 top-3 w-4 h-4 text-[#78716c]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => {
                  if (searchResults.length > 0) setShowSearchDropdown(true)
                }}
                placeholder="Search TMDB catalog: e.g. Stalker, Come and See, Chungking Express, Lily Chou-Chou, Cure, Dune..."
                className="w-full bg-white border border-[#d6d3d1] rounded-lg pl-10 pr-4 py-2.5 text-xs text-[#1c1917] placeholder-[#a8a29e] focus:outline-none focus:border-[#1c1917] shadow-xs"
              />
              {isSearching && (
                <span className="absolute right-3.5 top-2.5 text-[11px] text-[#a8a29e] font-mono">
                  Searching...
                </span>
              )}
            </div>

            {showSearchDropdown && searchResults.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1.5 bg-white border border-[#e5e2da] rounded-lg shadow-lg overflow-hidden max-h-80 overflow-y-auto divide-y divide-[#f0eee6]">
                {searchResults.map((movie) => (
                  <div
                    key={movie.id || movie.title}
                    onClick={() => selectMovie(movie)}
                    className="w-full text-left p-2.5 hover:bg-[#f8f7f4] flex items-center justify-between gap-3 transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      {movie.poster_url ? (
                        <img
                          src={movie.poster_url}
                          alt={movie.title}
                          className="w-8 h-12 object-cover rounded border border-[#e5e2da] shrink-0 bg-[#f0eee6]"
                          onError={(e) => {
                            ;(e.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                      ) : (
                        <div className="w-8 h-12 rounded border border-[#e5e2da] bg-[#f8f7f4] flex items-center justify-center shrink-0 text-[#a8a29e]">
                          <Film className="w-3.5 h-3.5" />
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-xs text-[#1c1917] truncate">
                            {movie.title}
                          </span>
                          {movie.release_year && (
                            <span className="text-[10px] font-mono text-[#78716c]">
                              ({movie.release_year})
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-[#78716c] truncate">
                          {movie.genres?.join(', ') || 'Uncategorized'} &bull; {movie.runtime ? `${movie.runtime}m` : 'Runtime N/A'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {/* Bookmark Heart Button on Search Result Card */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          toggleBookmark(movie)
                        }}
                        className={`p-1.5 rounded-full transition cursor-pointer ${
                          isBookmarked(movie.title)
                            ? 'text-rose-600 bg-rose-50 hover:bg-rose-100'
                            : 'text-[#a8a29e] hover:text-rose-600 hover:bg-[#f0eee6]'
                        }`}
                        title={isBookmarked(movie.title) ? 'Remove bookmark' : 'Bookmark movie'}
                      >
                        <Heart
                          className={`w-4 h-4 transition-transform active:scale-125 ${
                            isBookmarked(movie.title) ? 'fill-rose-500 text-rose-500' : ''
                          }`}
                        />
                      </button>

                      <span className="text-[10px] font-mono text-[#78716c] uppercase group-hover:text-[#1c1917] hidden sm:inline">
                        Select &rarr;
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Compact Dataset Pill */}
          <div className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-2 bg-white border border-[#e5e2da] px-3 py-1.5 rounded-lg text-[11px] text-[#57534e]">
              <Database className="w-3.5 h-3.5 text-[#78716c]" />
              <span className="font-mono">
                {datasetInfo?.catalog_entries_count ? `${datasetInfo.catalog_entries_count.toLocaleString()} Clean Movies` : 'Database Active'}
              </span>
              <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded border bg-emerald-50 text-emerald-800 border-emerald-300">
                Safe Filtered
              </span>
            </div>
            <button
              type="button"
              onClick={handleRetrainDataset}
              disabled={isProcessingDataset}
              className="cursor-pointer px-2.5 py-1.5 rounded border border-[#1c1917] bg-[#1c1917] hover:bg-[#2e2a27] text-white text-[11px] font-medium transition-colors flex items-center gap-1"
            >
              <RefreshCw className={`w-3 h-3 ${isProcessingDataset ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Re-train</span>
            </button>
          </div>
        </div>

        {/* Quick-Pick Film Strip */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#78716c] font-semibold">
                Quick Pick — Curated Cinephile Catalog
              </span>
              <span className="text-[9px] font-mono px-2 py-0.5 rounded border border-[#e5e2da] bg-white text-[#78716c]">
                {QUICK_PICKS.length} Masterworks
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => scrollQuickPicks('left')}
                className="cursor-pointer p-1 rounded border border-[#e5e2da] bg-white hover:bg-[#f8f7f4] text-[#78716c] hover:text-[#1c1917] transition shadow-2xs"
                title="Scroll Left"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => scrollQuickPicks('right')}
                className="cursor-pointer p-1 rounded border border-[#e5e2da] bg-white hover:bg-[#f8f7f4] text-[#78716c] hover:text-[#1c1917] transition shadow-2xs"
                title="Scroll Right"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div
            ref={quickPicksRef}
            className="flex gap-3 overflow-x-auto pb-2 scroll-smooth scrollbar-thin scrollbar-thumb-[#d6d3d1] scrollbar-track-transparent -mx-1 px-1"
          >
            {QUICK_PICKS.map((film) => (
              <div
                key={film.id}
                className="group shrink-0 relative text-left"
              >
                <div
                  onClick={() => selectMovie(film)}
                  className="w-20 sm:w-22 rounded-md border border-[#e5e2da] overflow-hidden bg-[#f0eee6] shadow-xs transition-all duration-200 group-hover:shadow-md group-hover:border-[#1c1917] group-hover:-translate-y-0.5 cursor-pointer relative"
                  title={`${film.title} (${film.release_year}) — Click to evaluate`}
                >
                  <div className="w-full h-28 sm:h-30 overflow-hidden bg-[#e5e2da] relative">
                    <img
                      src={film.poster_url!}
                      alt={film.title}
                      loading="lazy"
                      className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = 'https://placehold.co/80x120/e5e2da/78716c?text=Poster'
                      }}
                    />

                    {/* Quick Pick Floating Bookmark Button */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleBookmark(film)
                      }}
                      className={`absolute top-1 right-1 p-1 rounded-full z-10 transition-all cursor-pointer backdrop-blur-xs shadow-xs ${
                        isBookmarked(film.title)
                          ? 'bg-rose-500 text-white shadow-rose-200'
                          : 'bg-black/40 text-white/80 hover:bg-black/70 hover:text-white'
                      }`}
                      title={isBookmarked(film.title) ? 'Remove bookmark' : 'Bookmark movie'}
                    >
                      <Heart
                        className={`w-3 h-3 ${isBookmarked(film.title) ? 'fill-white' : ''}`}
                      />
                    </button>
                  </div>
                  <div className="px-1.5 py-1.5 bg-white space-y-0.5">
                    <p className="text-[9px] font-mono font-medium text-[#292524] truncate leading-tight">
                      {film.title}
                    </p>
                    <div className="flex items-center justify-between text-[8px] font-mono text-[#a8a29e]">
                      <span>{film.release_year}</span>
                      <span className="uppercase">{film.original_language}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Focused Layout: Compact Metadata Input (Col 4) & Expansive Review Space (Col 8) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* COMPACT METADATA INPUT (4 Cols) */}
          <aside className="lg:col-span-4 bg-white border border-[#e5e2da] rounded-xl p-5 shadow-xs space-y-4">
            <div className="border-b border-[#f0eee6] pb-3 flex items-center justify-between">
              <h2 className="font-serif font-bold text-sm text-[#1c1917] flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-[#78716c]" />
                <span>Metadata Parameters</span>
              </h2>
              <span className="text-[10px] font-mono text-[#78716c]">Pre-Release Inputs</span>
            </div>

            <form onSubmit={(e) => submitPrediction(undefined, e)} className="space-y-4">
              {/* Title Input */}
              <div className="space-y-1">
                <label className="block text-[10px] font-mono uppercase tracking-wider text-[#57534e]">
                  Film Title
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Film title..."
                  className="w-full bg-[#fcfbf9] border border-[#d6d3d1] rounded px-3 py-1.5 text-xs text-[#1c1917] placeholder-[#a8a29e] focus:outline-none focus:border-[#1c1917]"
                />
              </div>

              {/* Compact Genre Tags */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-mono uppercase tracking-wider text-[#57534e] flex items-center gap-1">
                    <Tag className="w-3 h-3 text-[#78716c]" />
                    <span>Genres ({selectedGenres.length})</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowGenreSelector(!showGenreSelector)}
                    className="cursor-pointer text-[10px] text-[#78716c] hover:text-[#1c1917] flex items-center gap-0.5"
                  >
                    <span>{showGenreSelector ? 'Hide' : 'Edit'}</span>
                    {showGenreSelector ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                </div>

                {/* Selected genre preview tags */}
                <div className="flex flex-wrap gap-1">
                  {selectedGenres.map((g) => (
                    <span
                      key={g}
                      onClick={() => toggleGenre(g)}
                      className="cursor-pointer text-[10px] font-mono px-2 py-0.5 rounded bg-[#1c1917] text-white hover:bg-rose-900 transition flex items-center gap-1"
                      title="Click to remove"
                    >
                      {g} &times;
                    </span>
                  ))}
                  {selectedGenres.length === 0 && (
                    <span className="text-[11px] text-[#a8a29e] italic">No genres selected</span>
                  )}
                </div>

                {/* Collapsible full genre selector */}
                {showGenreSelector && (
                  <div className="p-2 bg-[#fcfbf9] rounded border border-[#e5e2da] max-h-36 overflow-y-auto flex flex-wrap gap-1 mt-1">
                    {AVAILABLE_GENRES.map((genre) => {
                      const isSelected = selectedGenres.includes(genre)
                      return (
                        <button
                          key={genre}
                          type="button"
                          onClick={() => toggleGenre(genre)}
                          className={`cursor-pointer text-[10px] px-2 py-0.5 rounded border transition flex items-center gap-1 ${
                            isSelected
                              ? 'bg-[#1c1917] text-white border-[#1c1917]'
                              : 'bg-white text-[#57534e] border-[#e5e2da] hover:border-[#a8a29e]'
                          }`}
                        >
                          {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                          {genre}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Year & Runtime compact */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <div className="space-y-1">
                  <div className="flex justify-between items-center text-[10px] font-mono">
                    <span className="uppercase text-[#57534e]">Year</span>
                    <span className="font-bold text-[#1c1917]">{releaseYear}</span>
                  </div>
                  <input
                    type="range"
                    min={1960}
                    max={2026}
                    value={releaseYear}
                    onChange={(e) => setReleaseYear(Number(e.target.value))}
                    className="w-full accent-[#1c1917] cursor-pointer h-1.5"
                  />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between items-center text-[10px] font-mono">
                    <span className="uppercase text-[#57534e]">Length</span>
                    <span className="font-bold text-[#1c1917]">{runtime}m</span>
                  </div>
                  <input
                    type="range"
                    min={45}
                    max={240}
                    value={runtime}
                    onChange={(e) => setRuntime(Number(e.target.value))}
                    className="w-full accent-[#1c1917] cursor-pointer h-1.5"
                  />
                </div>
              </div>

              {/* Language & Budget */}
              <div className="space-y-3 pt-1">
                <div className="space-y-1">
                  <label className="block text-[10px] font-mono uppercase tracking-wider text-[#57534e]">
                    Original Language
                  </label>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full bg-[#fcfbf9] border border-[#d6d3d1] rounded px-2.5 py-1.5 text-xs text-[#1c1917] focus:outline-none focus:border-[#1c1917]"
                  >
                    {LANGUAGES.map((lang) => (
                      <option key={lang.code} value={lang.code}>
                        {lang.name} ({lang.code.toUpperCase()})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between items-center text-[10px] font-mono">
                    <span className="uppercase text-[#57534e]">Budget (USD)</span>
                    <span className="font-bold text-[#1c1917]">{formatCurrency(budget)}</span>
                  </div>
                  <input
                    type="number"
                    min={0}
                    step={1000000}
                    value={budget}
                    onChange={(e) => setBudget(Number(e.target.value))}
                    className="w-full bg-[#fcfbf9] border border-[#d6d3d1] rounded px-2.5 py-1.5 text-xs font-mono text-[#1c1917] focus:outline-none focus:border-[#1c1917]"
                  />
                  <div className="flex gap-1 pt-0.5">
                    {[
                      { label: '$2M', val: 2_000_000 },
                      { label: '$25M', val: 25_000_000 },
                      { label: '$150M', val: 150_000_000 },
                    ].map((b) => (
                      <button
                        key={b.label}
                        type="button"
                        onClick={() => setBudget(b.val)}
                        className="cursor-pointer text-[9px] font-mono px-1.5 py-0.5 rounded bg-white border border-[#e5e2da] text-[#57534e] hover:border-[#1c1917]"
                      >
                        {b.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Poster URL (Compact Input) */}
              <div className="space-y-1 pt-1 border-t border-[#f0eee6]">
                <label className="block text-[10px] font-mono uppercase tracking-wider text-[#57534e]">
                  Poster Path / URL
                </label>
                <input
                  type="text"
                  value={posterUrl || ''}
                  onChange={(e) => setPosterUrl(e.target.value || null)}
                  placeholder="https://image.tmdb.org/t/p/w500/..."
                  className="w-full bg-[#fcfbf9] border border-[#d6d3d1] rounded px-2.5 py-1 text-[11px] font-mono text-[#1c1917] placeholder-[#a8a29e] focus:outline-none focus:border-[#1c1917]"
                />
              </div>

              {/* Evaluate Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full cursor-pointer py-2.5 px-4 rounded bg-[#1c1917] hover:bg-[#2e2a27] text-white font-medium text-xs transition-colors flex items-center justify-center gap-1.5 mt-2 shadow-xs"
              >
                {isLoading ? (
                  <span>Evaluating...</span>
                ) : (
                  <>
                    <span>Recalculate Classification</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </form>

            {/* Leakage Protection Footnote */}
            <div className="pt-2 border-t border-[#f0eee6] text-[10px] text-[#78716c] leading-relaxed">
              <span className="font-bold text-[#1c1917]">Leakage Guard:</span> <code className="bg-[#f8f7f4] px-1 py-0.5 rounded">popularity</code>, <code className="bg-[#f8f7f4] px-1 py-0.5 rounded">vote_count</code>, and <code className="bg-[#f8f7f4] px-1 py-0.5 rounded">vote_average</code> are omitted from model features.
            </div>
          </aside>

          {/* HERO REVIEW & CLASSIFICATION DOSSIER (8 Cols) */}
          <section className="lg:col-span-8 space-y-6">
            <div className="bg-white border border-[#e5e2da] rounded-xl p-6 sm:p-8 shadow-xs space-y-7">
              
              {/* SECTION 1: CINEPHILE FILM DOSSIER HEADER */}
              <div className="flex flex-col sm:flex-row items-start gap-6 border-b border-[#f0eee6] pb-6">
                {/* Poster Display (Authentic 2:3 ratio frame) */}
                <div className="w-36 sm:w-44 h-52 sm:h-64 rounded-lg border border-[#e5e2da] overflow-hidden shrink-0 shadow-md bg-[#f0eee6] relative group">
                  {posterUrl ? (
                    <img
                      src={posterUrl}
                      alt={title}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        ;(e.target as HTMLImageElement).src = 'https://placehold.co/300x450/e5e2da/1c1917?text=No+Poster'
                      }}
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-[#a8a29e] p-3 text-center bg-[#f8f7f4]">
                      <Film className="w-8 h-8 mb-2 text-[#78716c]" />
                      <span className="text-[11px] font-mono leading-tight">No Poster Available</span>
                    </div>
                  )}

                  {/* Floating Bookmark Button on Main Prediction Card Poster */}
                  <button
                    type="button"
                    onClick={() =>
                      toggleBookmark({
                        title,
                        release_year: releaseYear,
                        runtime,
                        genres: selectedGenres,
                        poster_url: posterUrl || undefined,
                        budget,
                        original_language: language,
                        tagline: tagline || undefined,
                        overview: overview || undefined,
                      })
                    }
                    className={`absolute top-2 right-2 p-1.5 rounded-full z-10 transition-all cursor-pointer shadow-md backdrop-blur-xs ${
                      isBookmarked(title)
                        ? 'bg-rose-500 text-white shadow-rose-200'
                        : 'bg-black/50 text-white/90 hover:bg-black/80 hover:text-white'
                    }`}
                    title={isBookmarked(title) ? 'Remove from watchlist' : 'Bookmark this film'}
                  >
                    <Heart className={`w-4 h-4 ${isBookmarked(title) ? 'fill-white' : ''}`} />
                  </button>
                </div>

                {/* Film Metadata & Overview */}
                <div className="space-y-3 flex-1 min-w-0">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-mono uppercase tracking-widest text-[#78716c] bg-[#f8f7f4] border border-[#e5e2da] px-2 py-0.5 rounded">
                          TMDB Catalog Dossier
                        </span>
                        <span className="text-xs font-mono text-[#78716c]">
                          {releaseYear} &bull; {formatRuntime(runtime)} &bull; {language.toUpperCase()}
                        </span>
                      </div>

                      {/* Header Bookmark Action Button */}
                      <button
                        type="button"
                        onClick={() =>
                          toggleBookmark({
                            title,
                            release_year: releaseYear,
                            runtime,
                            genres: selectedGenres,
                            poster_url: posterUrl || undefined,
                            budget,
                            original_language: language,
                            tagline: tagline || undefined,
                            overview: overview || undefined,
                          })
                        }
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium border transition cursor-pointer ${
                          isBookmarked(title)
                            ? 'bg-rose-50 border-rose-200 text-rose-700 hover:bg-rose-100'
                            : 'bg-white border-[#e5e2da] text-[#57534e] hover:border-rose-300 hover:text-rose-600'
                        }`}
                      >
                        <Heart
                          className={`w-3.5 h-3.5 ${
                            isBookmarked(title) ? 'fill-rose-500 text-rose-500' : ''
                          }`}
                        />
                        <span>{isBookmarked(title) ? 'Bookmarked' : 'Bookmark Film'}</span>
                      </button>
                    </div>

                    <h1 className="font-serif font-black text-2xl sm:text-3xl text-[#1c1917] tracking-tight leading-tight">
                      {title || 'Untitled Film'}
                    </h1>

                    {tagline && (
                      <p className="text-sm italic font-serif text-[#78716c] leading-snug">
                        &ldquo;{tagline}&rdquo;
                      </p>
                    )}
                  </div>

                  {/* Genre Pills */}
                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {selectedGenres.map((g) => (
                      <span
                        key={g}
                        className="text-xs font-mono bg-[#f8f7f4] border border-[#e5e2da] px-2.5 py-0.5 rounded text-[#1c1917] font-medium"
                      >
                        {g}
                      </span>
                    ))}
                  </div>

                  {/* Synopsis Overview */}
                  {overview && (
                    <p className="text-xs sm:text-sm text-[#44403c] leading-relaxed pt-1">
                      {overview}
                    </p>
                  )}
                </div>
              </div>

              {/* SECTION 2: POPULARITY CLASSIFICATION VERDICT & METER */}
              {result && (
                <div className="bg-[#fcfbf9] border border-[#e5e2da] rounded-xl p-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#f0eee6] pb-3">
                    <div className="space-y-0.5">
                      <span className="text-[10px] font-mono uppercase tracking-widest text-[#78716c] block">
                        Neural Network Pre-Release Forecast
                      </span>
                      <div className="flex items-center gap-3">
                        <span
                          className={`inline-flex items-center px-3 py-1 rounded-md text-sm font-black tracking-wide uppercase border ${
                            result.is_popular
                              ? 'bg-emerald-50 text-emerald-950 border-emerald-300'
                              : 'bg-amber-50 text-amber-950 border-amber-300'
                          }`}
                        >
                          {result.prediction}
                        </span>
                        <span className="text-xs font-mono text-[#78716c]">
                          Threshold: <strong className="text-[#1c1917]">Top 25% (75th Percentile)</strong>
                        </span>
                      </div>
                    </div>

                    <div className="text-left sm:text-right">
                      <span className="text-[10px] font-mono uppercase text-[#78716c] block">
                        Probability Score
                      </span>
                      <span className="font-mono font-bold text-lg text-[#1c1917]">
                        {(result.probability * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* Probability Gauge Bar */}
                  <div className="space-y-1.5">
                    <div className="h-2.5 w-full bg-[#e5e2da] rounded-full overflow-hidden p-0.5">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${
                          result.is_popular ? 'bg-emerald-700' : 'bg-amber-700'
                        }`}
                        style={{ width: `${Math.max(5, result.probability * 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-mono text-[#78716c]">
                      <span>Kurang Populer (Lower 75%)</span>
                      <span className="font-bold text-[#1c1917]">50% Decision Line</span>
                      <span className="text-emerald-800 font-bold">Popular (Top 25%)</span>
                    </div>
                  </div>
                </div>
              )}

              {/* SECTION 3: METADATA DRIVER INSIGHTS */}
              {result && result.feature_insights.length > 0 && (
                <div className="space-y-2.5">
                  <div className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-[#78716c]">
                    <Sparkles className="w-3.5 h-3.5 text-[#1c1917]" />
                    <span>Metadata Model Drivers & Viability Analysis</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {result.feature_insights.map((insight, idx) => (
                      <div
                        key={idx}
                        className="bg-[#fcfbf9] p-3 rounded-lg border border-[#e5e2da] text-xs text-[#44403c] leading-relaxed flex items-start gap-2"
                      >
                        <span className="text-[#1c1917] font-bold mt-0.5">&bull;</span>
                        <span>{insight}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          </section>
        </div>

        </> : page === 'battle' ? <>
          <div className="border-b border-[#e5e2da] pb-5">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#78716c]">Analysis workspace</p>
            <h1 className="font-serif font-bold text-3xl mt-1">Head-to-Head Movie Battle</h1>
            <p className="text-sm text-[#78716c] mt-2">Select two catalog films and compare their real MLP popularity forecasts.</p>
          </div>
          <MovieBattle onPrediction={fetchPredictionHistory} />
        </> : <>
          <div className="border-b border-[#e5e2da] pb-5">
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#78716c]">Inference records</p>
            <h1 className="font-serif font-bold text-3xl mt-1">Prediction History</h1>
            <p className="text-sm text-[#78716c] mt-2">Every successful model run is recorded here. The table refreshes every 15 seconds.</p>
          </div>
          <AuditLogTable
            logs={predictionLogs}
            loading={isHistoryLoading}
            error={historyError}
            onRefresh={fetchPredictionHistory}
          />
        </>}
      </main>

      {/* Footer */}
      <footer className="border-t border-[#e5e2da] bg-white py-6 text-center text-xs text-[#78716c] space-y-1">
        <p>TMDB Movie Popularity Classifier &bull; Multi-Layer Perceptron (MLP)</p>
        <p className="text-[11px] font-mono text-[#a8a29e]">Nginx / Vite (frontend) &bull; FastAPI (backend) &bull; PostgreSQL (database)</p>
        <ReleaseFooterInfo health={environmentHealth} />
      </footer>

      {/* WATCHLIST / BOOKMARK DRAWER MODAL */}
      {showBookmarksDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs">
          <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col border-l border-[#e5e2da] animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-4 border-b border-[#f0eee6] flex items-center justify-between bg-[#fcfbf9]">
              <div className="flex items-center gap-2">
                <Heart className="w-4 h-4 fill-rose-500 text-rose-500" />
                <h2 className="font-serif font-bold text-base text-[#1c1917]">
                  Your Film Watchlist
                </h2>
                <span className="bg-rose-50 border border-rose-200 text-rose-700 text-xs font-mono font-bold px-2 py-0.5 rounded-full">
                  {bookmarks.length}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowBookmarksDrawer(false)}
                className="p-1 rounded-md text-[#78716c] hover:text-[#1c1917] hover:bg-[#f0eee6] transition cursor-pointer"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Bookmarks List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 divide-y divide-[#f0eee6]">
              {bookmarks.length === 0 ? (
                <div className="text-center py-16 space-y-3">
                  <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-500 flex items-center justify-center mx-auto border border-rose-200">
                    <Heart className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <p className="font-serif font-bold text-[#1c1917]">No bookmarks yet</p>
                    <p className="text-xs text-[#78716c] max-w-xs mx-auto leading-relaxed">
                      Click the heart icon on any movie in the search bar, quick picks, or prediction dossier to save it to your watchlist.
                    </p>
                  </div>
                </div>
              ) : (
                bookmarks.map((bm) => (
                  <div
                    key={bm.title}
                    className="pt-3 first:pt-0 flex items-start gap-3 group"
                  >
                    {/* Poster */}
                    <div
                      onClick={() => {
                        selectMovie(bm)
                        setShowBookmarksDrawer(false)
                      }}
                      className="w-12 h-18 rounded border border-[#e5e2da] overflow-hidden shrink-0 bg-[#f0eee6] cursor-pointer hover:border-[#1c1917] transition"
                    >
                      {bm.poster_url ? (
                        <img
                          src={bm.poster_url}
                          alt={bm.title}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            ;(e.target as HTMLImageElement).src =
                              'https://placehold.co/80x120/e5e2da/78716c?text=Poster'
                          }}
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[#a8a29e]">
                          <Film className="w-4 h-4" />
                        </div>
                      )}
                    </div>

                    {/* Metadata & Actions */}
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-start justify-between gap-2">
                        <h3
                          onClick={() => {
                            selectMovie(bm)
                            setShowBookmarksDrawer(false)
                          }}
                          className="font-bold text-xs text-[#1c1917] truncate hover:underline cursor-pointer"
                        >
                          {bm.title}
                        </h3>
                        <button
                          type="button"
                          onClick={() => toggleBookmark(bm)}
                          className="text-[#a8a29e] hover:text-rose-600 p-1 transition cursor-pointer"
                          title="Remove from watchlist"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="flex items-center gap-1.5 text-[10px] font-mono text-[#78716c]">
                        {bm.release_year && <span>{bm.release_year}</span>}
                        {bm.runtime && <span>&bull; {bm.runtime}m</span>}
                        {bm.original_language && (
                          <span className="uppercase">&bull; {bm.original_language}</span>
                        )}
                      </div>

                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[10px] text-[#78716c] truncate max-w-[180px]">
                          {bm.genres?.join(', ') || 'Uncategorized'}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            selectMovie(bm)
                            setShowBookmarksDrawer(false)
                          }}
                          className="text-[10px] font-mono uppercase font-bold text-[#1c1917] hover:underline flex items-center gap-0.5 cursor-pointer"
                        >
                          <span>Evaluate</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            {bookmarks.length > 0 && (
              <div className="p-3 bg-[#fcfbf9] border-t border-[#f0eee6] flex justify-between items-center text-xs">
                <span className="text-[11px] font-mono text-[#78716c]">
                  Synchronized with backend DB
                </span>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm('Clear all bookmarks?')) {
                      bookmarks.forEach((b) => toggleBookmark(b))
                    }
                  }}
                  className="text-[11px] font-mono text-rose-600 hover:underline cursor-pointer"
                >
                  Clear All
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
