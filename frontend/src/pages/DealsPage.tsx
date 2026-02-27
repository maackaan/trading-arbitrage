import { useCallback, useEffect, useState } from 'react'

import { fetchDeals, fetchHealth } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { DealItem, RealtimeEvent } from '../types'

export function DealsPage() {
  const [market, setMarket] = useState('csmoney')
  const [minDiscount, setMinDiscount] = useState(5)
  const [sinceHours, setSinceHours] = useState(24)
  const [deals, setDeals] = useState<DealItem[]>([])
  const [loading, setLoading] = useState(false)
  const [appliedFilters, setAppliedFilters] = useState({ market: 'csmoney', minDiscount: 5, sinceHours: 24 })
  const [csmoneyConfigured, setCsmoneyConfigured] = useState(true)
  const { subscribe } = useRealtime()

  const load = useCallback(async (filters: { market: string; minDiscount: number; sinceHours: number }) => {
    setLoading(true)
    try {
      const rows = await fetchDeals({
        market: filters.market || undefined,
        minDiscount: filters.minDiscount,
        sinceHours: filters.sinceHours,
      })
      setDeals(rows)
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
        if (event.event === 'deal_alert') {
          void load(appliedFilters)
        }
      }),
    [appliedFilters, load, subscribe],
  )

  useEffect(() => {
    void fetchHealth()
      .then((value) => setCsmoneyConfigured(value.csmoney_listings_api_configured))
      .catch(() => setCsmoneyConfigured(false))
  }, [])

  return (
    <section className="page">
      <h1>Deals feed</h1>
      <p className="muted">
        Underpriced real listings versus Buff163 and rolling market mean.
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
        <button
          className="button"
          onClick={() => {
            setAppliedFilters({ market, minDiscount, sinceHours })
          }}
        >
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
      {!loading && deals.length === 0 ? (
        <p className="muted">
          No real deals found for this filter.
          {appliedFilters.market.trim().toLowerCase() === 'csmoney' && !csmoneyConfigured
            ? ' CS.MONEY direct recent-feed API is not configured, so unverified rows are hidden.'
            : ''}
        </p>
      ) : null}
    </section>
  )
}
