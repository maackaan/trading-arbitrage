import { useCallback, useEffect, useState } from 'react'

import { fetchDeals, fetchHealth, fetchProviderStatus } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { DealItem, RealtimeEvent } from '../types'

export function DealsPage() {
  const [market, setMarket] = useState('csgofloat')
  const [minDiscount, setMinDiscount] = useState(5)
  const [sinceHours, setSinceHours] = useState(24)
  const [deals, setDeals] = useState<DealItem[]>([])
  const [loading, setLoading] = useState(false)
  const [appliedFilters, setAppliedFilters] = useState({ market: 'csgofloat', minDiscount: 5, sinceHours: 24 })
  const [csfloatConfigured, setCsfloatConfigured] = useState(true)
  const [csfloatAuthConfigured, setCsfloatAuthConfigured] = useState(true)
  const [csfloatError, setCsfloatError] = useState<string | null>(null)
  const [csfloatCooldownUntil, setCsfloatCooldownUntil] = useState<string | null>(null)
  const { subscribe } = useRealtime()

  const refreshHealth = useCallback(async () => {
    try {
      const [health, status] = await Promise.all([fetchHealth(), fetchProviderStatus()])
      const csfloat = status.providers.find((provider) => provider.name === 'csgofloat')
      setCsfloatConfigured(health.csfloat_listings_api_configured)
      setCsfloatAuthConfigured(health.csfloat_auth_configured)
      setCsfloatError(csfloat?.last_listing_error ?? csfloat?.last_price_error ?? health.csfloat_last_error)
      setCsfloatCooldownUntil(csfloat?.cooldown_until ?? null)
    } catch {
      setCsfloatConfigured(false)
      setCsfloatAuthConfigured(false)
      setCsfloatError(null)
      setCsfloatCooldownUntil(null)
    }
  }, [])

  const load = useCallback(async (filters: { market: string; minDiscount: number; sinceHours: number }) => {
    setLoading(true)
    try {
      const [rows] = await Promise.all([
        fetchDeals({
          market: filters.market || undefined,
          minDiscount: filters.minDiscount,
          sinceHours: filters.sinceHours,
        }),
        refreshHealth(),
      ])
      setDeals(rows)
    } finally {
      setLoading(false)
    }
  }, [refreshHealth])

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
    void refreshHealth()
  }, [refreshHealth])

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
      {appliedFilters.market.trim().toLowerCase() === 'csgofloat' && !csfloatAuthConfigured ? (
        <p className="notice">
          CSFloat listings require authentication. Set <code>CSGOFLOAT_API_KEY</code> or <code>CSFLOAT_SESSION_COOKIE</code> in <code>backend/.env</code>, then restart the backend.
        </p>
      ) : null}
      {appliedFilters.market.trim().toLowerCase() === 'csgofloat' && csfloatCooldownUntil ? (
        <p className="notice">
          CSFloat is cooling down until {new Date(csfloatCooldownUntil).toLocaleString()}. This usually means CSFloat returned a rate-limit or auth error, not that listings do not exist.
        </p>
      ) : null}
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
                  Discount vs {deal.reference_market?.toUpperCase() ?? 'baseline'}:{' '}
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
                <div className="muted">
                  Ref{deal.reference_market ? ` (${deal.reference_market})` : ''}: {deal.reference_price.toFixed(2)} USD
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {!loading && deals.length === 0 ? (
        <p className="muted">
          No real deals found for this filter.
          {appliedFilters.market.trim().toLowerCase() === 'csgofloat' && !csfloatConfigured
            ? ' CSFloat listings API is not configured, so no real CSFloat listings can be shown.'
            : ''}
          {appliedFilters.market.trim().toLowerCase() === 'csgofloat' && csfloatConfigured && !csfloatAuthConfigured
            ? ' CSFloat auth is not configured, so protected CSFloat listings cannot be fetched.'
            : ''}
          {appliedFilters.market.trim().toLowerCase() === 'csgofloat' && csfloatError
            ? ` CSFloat error: ${csfloatError}`
            : ''}
        </p>
      ) : null}
    </section>
  )
}
