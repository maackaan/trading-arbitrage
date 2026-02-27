import { useCallback, useEffect, useState } from 'react'

import { fetchDeals } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { DealItem, RealtimeEvent } from '../types'

export function DealsPage() {
  const [market, setMarket] = useState('csmoney')
  const [minDiscount, setMinDiscount] = useState(15)
  const [sinceHours, setSinceHours] = useState(24)
  const [deals, setDeals] = useState<DealItem[]>([])
  const [loading, setLoading] = useState(false)
  const { subscribe } = useRealtime()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await fetchDeals({ market: market || undefined, minDiscount, sinceHours })
      setDeals(rows)
    } finally {
      setLoading(false)
    }
  }, [market, minDiscount, sinceHours])

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
      <p className="muted">
        Underpriced listings versus Buff163 and rolling market mean. Rows now prefer csgoskins-backed market prices when available.
      </p>
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
        <button className="button" onClick={() => void load()}>
          Apply
        </button>
      </div>

      {loading ? <p className="muted">Loading deals...</p> : null}
      <ul className="list">
        {deals.map((deal) => (
          <li key={deal.listing_id} className={deal.extreme_underpricing ? 'item extreme' : 'item'}>
            <div className="listing-row">
              {deal.image_url ? <img className="listing-thumb" src={deal.image_url} alt={deal.skin_name} /> : null}
              <div>
                <div>
                  <strong>{deal.skin_name}</strong> <span className="muted">({deal.market})</span>
                </div>
                <div className="muted">
                  Listed: {new Date(deal.listed_at).toLocaleString()}
                  {deal.price_source ? ` | Source: ${deal.price_source}` : ''}
                </div>
                <div className="muted">
                  Discount vs Buff163:{' '}
                  {deal.discount_vs_buff_pct !== null ? `${deal.discount_vs_buff_pct.toFixed(2)}%` : 'n/a'}
                  {deal.discount_vs_rolling_pct !== null ? ` | vs rolling: ${deal.discount_vs_rolling_pct.toFixed(2)}%` : ''}
                </div>
              </div>
            </div>
            <div className="price-col">
              <div>
                {deal.price.toFixed(2)} {deal.currency}
              </div>
              {deal.reference_price !== null ? (
                <div className="muted">Ref: {deal.reference_price.toFixed(2)} USD</div>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
