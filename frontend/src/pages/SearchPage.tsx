import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { searchSkins } from '../api/client'
import type { Skin } from '../types'

export function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Skin[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const handle = setTimeout(() => {
      if (!query.trim()) {
        setResults([])
        return
      }

      setLoading(true)
      void searchSkins(query)
        .then(setResults)
        .finally(() => setLoading(false))
    }, 250)

    return () => clearTimeout(handle)
  }, [query])

  return (
    <section className="page">
      <h1>Search skins</h1>
      <input
        className="text-input"
        type="text"
        placeholder="AK-47 | Redline"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {loading ? <p className="muted">Searching...</p> : null}
      <ul className="list">
        {results.map((skin) => (
          <li key={skin.id}>
            <Link to={`/skins/${skin.id}`}>{skin.name}</Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
