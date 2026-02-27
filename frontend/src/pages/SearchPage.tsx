import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { searchSkins } from '../api/client'
import type { Skin } from '../types'

const EXAMPLE_QUERIES = [
  'AK-47 | Redline',
  'AWP | Asiimov',
  'Desert Eagle | Printstream',
  'USP-S | Kill Confirmed',
]

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Skin[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)

  const runSearch = useCallback(async (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) {
      setResults([])
      setHasSearched(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const rows = await searchSkins(trimmed)
      setResults(rows)
      setHasSearched(true)
    } catch {
      setError('Search failed. Check if backend is running.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const handle = setTimeout(() => {
      void runSearch(query)
    }, 250)

    return () => clearTimeout(handle)
  }, [query, runSearch])

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void runSearch(query)
  }

  return (
    <section className="page">
      <h1>Search skins</h1>
      <form className="search-form" onSubmit={onSubmit}>
        <input
          className="text-input"
          type="text"
          placeholder="Type a skin name (e.g. AK-47 | Redline)"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <div className="search-actions">
          <button className="button" type="submit">
            Search
          </button>
          <button
            className="button secondary"
            type="button"
            onClick={() => {
              setQuery('')
              setResults([])
              setHasSearched(false)
              setError(null)
            }}
          >
            Clear
          </button>
        </div>
      </form>
      <p className="muted">Try an example:</p>
      <div className="chip-row">
        {EXAMPLE_QUERIES.map((item) => (
          <button
            key={item}
            className="chip"
            type="button"
            onClick={() => {
              setQuery(item)
              void runSearch(item)
            }}
          >
            {item}
          </button>
        ))}
      </div>
      {loading ? <p className="muted">Searching...</p> : null}
      {error ? <p className="muted">{error}</p> : null}
      {hasSearched && !loading && !error && results.length === 0 ? (
        <p className="muted">No skins matched “{query.trim()}”. Try a broader term like “AK-47” or “Asiimov”.</p>
      ) : null}
      <ul className="list">
        {results.map((skin) => (
          <li key={skin.id} className="search-result">
            <Link to={`/skins/${skin.id}`}>{skin.name}</Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
