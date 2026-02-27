import { useCallback, useEffect, useState } from 'react'

import { fetchNewListings } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { ListingItem, RealtimeEvent } from '../types'

export function NewListingsPage() {
  const [market, setMarket] = useState('csmoney')
  const [sinceHours, setSinceHours] = useState(6)
  const [items, setItems] = useState<ListingItem[]>([])
  const [loading, setLoading] = useState(false)
  const [appliedFilters, setAppliedFilters] = useState({ market: 'csmoney', sinceHours: 6 })
  const { subscribe } = useRealtime()

  const load = useCallback(async (filters: { market: string; sinceHours: number }) => {
    setLoading(true)
    try {
      const rows = await fetchNewListings({
        market: filters.market || undefined,
        sinceHours: filters.sinceHours,
      })
      setItems(rows)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(appliedFilters)
  }, [appliedFilters, load])

  useEffect(
    () =>
      subscribe((event: RealtimeEvent) => {
        if (event.event === 'new_listing') {
          void load(appliedFilters)
        }
      }),
    [appliedFilters, load, subscribe],
  )

  return (
    <section className="page">
      <h1>New listings</h1>
      <p className="muted">Newest real listings first, sorted by listing time from source feed.</p>
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
        <button
          className="button"
          onClick={() => {
            setAppliedFilters({ market, sinceHours })
          }}
        >
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
          No real listings found for this filter.
          {appliedFilters.market.trim().toLowerCase() === 'csmoney'
            ? ' CS.MONEY direct recent-feed API is not configured, so unverified rows are hidden.'
            : ''}
        </p>
      ) : null}
    </section>
  )
}
