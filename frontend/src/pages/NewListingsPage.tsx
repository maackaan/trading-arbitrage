import { useCallback, useEffect, useState } from 'react'

import { fetchNewListings } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { ListingItem, RealtimeEvent } from '../types'

export function NewListingsPage() {
  const [market, setMarket] = useState('csmoney')
  const [sinceHours, setSinceHours] = useState(6)
  const [includeSimulated, setIncludeSimulated] = useState(true)
  const [items, setItems] = useState<ListingItem[]>([])
  const [loading, setLoading] = useState(false)
  const { subscribe } = useRealtime()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await fetchNewListings({ market: market || undefined, sinceHours, includeSimulated })
      setItems(rows)
    } finally {
      setLoading(false)
    }
  }, [market, sinceHours, includeSimulated])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(
    () =>
      subscribe((event: RealtimeEvent) => {
        if (event.event === 'new_listing') {
          void load()
        }
      }),
    [load, subscribe],
  )

  return (
    <section className="page">
      <h1>New listings</h1>
      <p className="muted">
        Newest listings first, sorted by listing time from source feed.
        {includeSimulated ? ' Includes simulated fallback listings.' : ' Showing only non-simulated listings.'}
      </p>
      <div className="filters">
        <label>
          Market
          <input className="text-input" value={market} onChange={(e) => setMarket(e.target.value)} placeholder="all" />
        </label>
        <label>
          Since (hours)
          <input
            className="text-input"
            type="number"
            value={sinceHours}
            onChange={(e) => setSinceHours(Number(e.target.value))}
            min={1}
            max={168}
          />
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={includeSimulated} onChange={(e) => setIncludeSimulated(e.target.checked)} />
          Include simulated
        </label>
        <button className="button" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {loading ? <p className="muted">Loading listings...</p> : null}
      <ul className="list">
        {items.map((item) => (
          <li key={item.listing_id} className={item.extreme_underpricing ? 'item extreme' : 'item'}>
            <div className="listing-row">
              {item.image_url ? <img className="listing-thumb" src={item.image_url} alt={item.skin_name} /> : null}
              <div>
                <div>
                  <strong>{item.skin_name}</strong> <span className="muted">({item.market})</span>
                </div>
                <div className="muted">
                  Listed: {new Date(item.listed_at).toLocaleString()} {item.is_deal ? '| Deal' : '| Normal'}
                </div>
                <div className="muted">
                  {item.price_source ? `Source: ${item.price_source}` : 'Source: n/a'}
                  {item.is_simulated ? ' | Simulated' : ''}
                </div>
              </div>
            </div>
            <div className="price-col">
              <div>
                {item.price.toFixed(2)} {item.currency}
              </div>
              {item.reference_price !== null ? (
                <div className="muted">Ref: {item.reference_price.toFixed(2)} USD</div>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {!loading && items.length === 0 ? (
        <p className="muted">
          No listings found for this filter. If you expected mock rows, enable “Include simulated”.
        </p>
      ) : null}
    </section>
  )
}
