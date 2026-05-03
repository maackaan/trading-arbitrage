import { useCallback, useEffect, useState } from 'react'

import { fetchHealth, fetchNewListings, fetchProviderStatus } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { ListingItem, RealtimeEvent } from '../types'

export function NewListingsPage() {
  const [market, setMarket] = useState('csgofloat')
  const [sinceHours, setSinceHours] = useState(6)
  const [items, setItems] = useState<ListingItem[]>([])
  const [loading, setLoading] = useState(false)
  const [appliedFilters, setAppliedFilters] = useState({ market: 'csgofloat', sinceHours: 6 })
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

  const load = useCallback(async (filters: { market: string; sinceHours: number }) => {
    setLoading(true)
    try {
      const [rows] = await Promise.all([
        fetchNewListings({
          market: filters.market || undefined,
          sinceHours: filters.sinceHours,
        }),
        refreshHealth(),
      ])
      setItems(rows)
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
        if (event.event === 'new_listing') {
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
                <div className="muted">
                  Ref{item.reference_market ? ` (${item.reference_market})` : ''}: {item.reference_price.toFixed(2)} USD
                </div>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {!loading && items.length === 0 ? (
        <p className="muted">
          No real listings found for this filter.
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
