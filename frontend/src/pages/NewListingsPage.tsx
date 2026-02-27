import { useCallback, useEffect, useState } from 'react'

import { fetchNewListings } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { ListingItem, RealtimeEvent } from '../types'

export function NewListingsPage() {
  const [market, setMarket] = useState('csmoney')
  const [items, setItems] = useState<ListingItem[]>([])
  const [loading, setLoading] = useState(false)
  const { subscribe } = useRealtime()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await fetchNewListings({ market: market || undefined })
      setItems(rows)
    } finally {
      setLoading(false)
    }
  }, [market])

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
      <p className="muted">All newly seen listings (deal and non-deal).</p>
      <div className="filters">
        <label>
          Market
          <input className="text-input" value={market} onChange={(e) => setMarket(e.target.value)} placeholder="all" />
        </label>
        <button className="button" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {loading ? <p className="muted">Loading listings...</p> : null}
      <ul className="list">
        {items.map((item) => (
          <li key={item.listing_id} className={item.extreme_underpricing ? 'item extreme' : 'item'}>
            <div>
              <strong>{item.skin_name}</strong> <span className="muted">({item.market})</span>
            </div>
            <div>
              {item.price.toFixed(2)} {item.currency}
            </div>
            <div className="muted">
              Listed: {new Date(item.listed_at).toLocaleString()} {item.is_deal ? '| Deal' : '| Normal'}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
