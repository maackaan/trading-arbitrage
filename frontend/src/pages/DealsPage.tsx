import { useCallback, useEffect, useState } from 'react'

import { fetchDeals } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { DealItem, RealtimeEvent } from '../types'

export function DealsPage() {
  const [market, setMarket] = useState('')
  const [minDiscount, setMinDiscount] = useState(10)
  const [deals, setDeals] = useState<DealItem[]>([])
  const [loading, setLoading] = useState(false)
  const { subscribe } = useRealtime()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await fetchDeals({ market: market || undefined, minDiscount })
      setDeals(rows)
    } finally {
      setLoading(false)
    }
  }, [market, minDiscount])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(
    () =>
      subscribe((event: RealtimeEvent) => {
        if (event.event === 'deal_alert') {
          void load()
        }
      }),
    [load, subscribe],
  )

  return (
    <section className="page">
      <h1>Deals feed</h1>
      <div className="filters">
        <label>
          Market
          <input className="text-input" value={market} onChange={(e) => setMarket(e.target.value)} placeholder="all" />
        </label>
        <label>
          Min discount %
          <input
            className="text-input"
            type="number"
            value={minDiscount}
            onChange={(e) => setMinDiscount(Number(e.target.value))}
            min={0}
          />
        </label>
        <button className="button" onClick={() => void load()}>
          Apply
        </button>
      </div>

      {loading ? <p className="muted">Loading deals...</p> : null}
      <ul className="list">
        {deals.map((deal) => (
          <li key={deal.listing_id} className={deal.extreme_underpricing ? 'item extreme' : 'item'}>
            <div>
              <strong>{deal.skin_name}</strong> <span className="muted">({deal.market})</span>
            </div>
            <div>
              {deal.price.toFixed(2)} {deal.currency}
            </div>
            <div className="muted">
              Discount vs Buff163:{' '}
              {deal.discount_vs_buff_pct !== null ? `${deal.discount_vs_buff_pct.toFixed(2)}%` : 'n/a'}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
