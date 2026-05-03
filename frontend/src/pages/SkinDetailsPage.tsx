import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { fetchSkinPrices, fetchSkinSummary, fetchSkinVariants } from '../api/client'
import { useRealtime } from '../components/useRealtime'
import type { PricePoint, RealtimeEvent, Skin, SkinSummary } from '../types'

const palette = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728', '#17becf', '#9467bd', '#8c564b', '#e377c2']
const sourceLabels: Record<string, string> = {
  steam: 'Steam lowest sell order',
  skinport: 'Skinport lowest live listing',
  csfloat: 'CSFloat lowest live listing',
}

function buildChartData(points: PricePoint[]) {
  const grouped = new Map<string, Record<string, number | string>>()

  points.forEach((point) => {
    const ts = new Date(point.timestamp).toISOString()
    if (!grouped.has(ts)) {
      grouped.set(ts, { timestamp: ts })
    }
    grouped.get(ts)![point.market] = point.price
  })

  return Array.from(grouped.values()).sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)))
}

function formatPrice(price: number | null, currency: string | null) {
  if (price === null || currency === null) {
    return 'No live price available'
  }
  return `${price.toFixed(2)} ${currency}`
}

export function SkinDetailsPage() {
  const { skinId } = useParams<{ skinId: string }>()
  const parsedSkinId = Number(skinId)
  const [summary, setSummary] = useState<SkinSummary | null>(null)
  const [points, setPoints] = useState<PricePoint[]>([])
  const [wearOptions, setWearOptions] = useState<Array<{ wear: string; skin: Skin }>>([])
  const [loading, setLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [imageBroken, setImageBroken] = useState(false)
  const { connected, subscribe, lastEventAt } = useRealtime()

  const load = useCallback(async () => {
    if (!Number.isFinite(parsedSkinId)) return
    setLoading(true)
    setHistoryError(null)
    try {
      const nextSummary = await fetchSkinSummary(parsedSkinId)
      setSummary(nextSummary)
      setImageBroken(false)

      const [pricesResult, variantsResult] = await Promise.allSettled([
        fetchSkinPrices(parsedSkinId, '7d'),
        fetchSkinVariants(parsedSkinId),
      ])

      if (pricesResult.status === 'fulfilled') {
        setPoints(pricesResult.value)
      } else {
        setPoints([])
        setHistoryError('Price history is temporarily unavailable.')
      }

      if (variantsResult.status === 'fulfilled') {
        const variantPayload = variantsResult.value
        setWearOptions(variantPayload.wear_options)
      } else {
        setWearOptions([])
      }
    } catch {
      setSummary(null)
      setPoints([])
      setWearOptions([])
      setHistoryError(null)
    } finally {
      setLoading(false)
    }
  }, [parsedSkinId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    let refreshTimer: ReturnType<typeof setTimeout> | null = null
    return subscribe((event: RealtimeEvent) => {
      if (event.event !== 'price_update') return
      if (Number(event.payload.skin_id) !== parsedSkinId) return

      if (refreshTimer) clearTimeout(refreshTimer)
      refreshTimer = setTimeout(() => {
        void load()
      }, 300)
    })
  }, [load, parsedSkinId, subscribe])

  const markets = useMemo(
    () => Array.from(new Set(points.map((point) => point.market))).sort(),
    [points],
  )
  const chartData = useMemo(() => buildChartData(points), [points])
  const heroImageUrl = summary?.image_url ?? summary?.skin.image_url ?? null

  if (!Number.isFinite(parsedSkinId)) {
    return <section className="page">Invalid skin id</section>
  }

  if (loading && !summary) {
    return <section className="page">Loading skin details...</section>
  }

  if (!summary) {
    return <section className="page">Skin not found.</section>
  }

  return (
    <section className="page">
      <h1>{summary.skin.name}</h1>
      <p className="muted">
        Realtime: {connected ? 'connected' : 'disconnected'}
        {lastEventAt ? ` | last event ${new Date(lastEventAt).toLocaleTimeString()}` : ''}
      </p>

      <div className="grid two-col details-top-grid">
        <article className="card">
          <h2>Item</h2>
          {heroImageUrl && !imageBroken ? (
            <img
              className="skin-hero"
              src={heroImageUrl}
              alt={summary.skin.name}
              onError={() => setImageBroken(true)}
            />
          ) : (
            <div className="skin-hero skin-hero-placeholder">Image unavailable</div>
          )}
        </article>

        <article className="card">
          <h2>Live price comparison</h2>
          <p>
            Item: <strong>{summary.price_comparison.item_name}</strong>
          </p>
          <ul className="list compact price-source-list">
            {summary.price_comparison.sources.map((source) => (
              <li key={source.source} className={!source.available ? 'unavailable' : undefined}>
                <span>{sourceLabels[source.source] ?? source.source}</span>
                <span>
                  {source.url && source.available ? (
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {formatPrice(source.price, source.currency)}
                    </a>
                  ) : (
                    formatPrice(source.price, source.currency)
                  )}
                  {source.available ? <small>Last updated: {new Date(source.last_updated).toLocaleString()}</small> : null}
                </span>
              </li>
            ))}
          </ul>
          {summary.price_comparison.cheapest_source ? (
            <p>
              Cheapest available source:{' '}
              <strong>
                {summary.price_comparison.cheapest_source.source} at{' '}
                {formatPrice(summary.price_comparison.cheapest_source.price, summary.price_comparison.cheapest_source.currency)}
              </strong>
            </p>
          ) : (
            <p className="muted">No live price available</p>
          )}
          <p className="muted">
            Difference between available sources:{' '}
            {summary.price_comparison.percentage_difference !== null
              ? `${summary.price_comparison.percentage_difference.toFixed(2)}%`
              : 'No live price available'}
          </p>
        </article>
      </div>

      <div className={`grid details-middle-grid ${wearOptions.length > 0 ? 'with-wear' : 'no-wear'}`}>
        {wearOptions.length > 0 ? (
          <article className="card">
            <h2>Switch wear</h2>
            <div className="wear-stack">
              {wearOptions.map((option) => (
                <Link
                  key={option.skin.id}
                  to={`/skins/${option.skin.id}`}
                  className={`chip-link wear-link ${option.skin.id === summary.skin.id ? 'active' : ''}`}
                >
                  {option.wear}
                </Link>
              ))}
            </div>
          </article>
        ) : null}

        <article className="card">
          <h2>Current prices</h2>
          <p>Buff163 baseline: {summary.baseline_price ? <strong>{summary.baseline_price.toFixed(2)} USD</strong> : 'No live price available'}</p>
          <ul className="list compact">
            {summary.latest_prices.length > 0 ? (
              summary.latest_prices.map((price) => (
                <li key={price.market}>
                  <span>{price.market}</span>
                  <span>
                    {price.url ? (
                      <a href={price.url} target="_blank" rel="noreferrer">
                        {price.price.toFixed(2)} {price.currency}
                      </a>
                    ) : (
                      `${price.price.toFixed(2)} ${price.currency}`
                    )}
                    {price.spread_vs_buff163_pct !== null
                      ? ` (${price.spread_vs_buff163_pct >= 0 ? '+' : ''}${price.spread_vs_buff163_pct.toFixed(2)}%)`
                      : ''}
                    <small>Last updated: {new Date(price.timestamp).toLocaleString()}</small>
                  </span>
                </li>
              ))
            ) : (
              <li>
                <span>All sources</span>
                <span>No live price available</span>
              </li>
            )}
          </ul>
        </article>
      </div>

      <article className="card chart-card">
        <h2>Price history (7d)</h2>
        {historyError ? <p className="muted">{historyError}</p> : null}
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(value) => new Date(String(value)).toLocaleDateString()}
              minTickGap={30}
            />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip labelFormatter={(value) => new Date(String(value)).toLocaleString()} />
            <Legend />
            {markets.map((market, index) => (
              <Line
                key={market}
                type="monotone"
                dataKey={market}
                stroke={palette[index % palette.length]}
                dot={false}
                strokeWidth={2}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </article>

      <article className="card">
        <h2>Metrics</h2>
        <table className="table">
          <thead>
            <tr>
              <th>Market</th>
              <th>Mean</th>
              <th>Rolling mean</th>
              <th>Spread vs Buff163</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.metrics_by_market).map(([market, metrics]) => (
              <tr key={market}>
                <td>{market}</td>
                <td>{metrics.mean_price.toFixed(2)}</td>
                <td>{metrics.rolling_mean_price.toFixed(2)}</td>
                <td>
                  {metrics.spread_vs_buff163_pct !== null
                    ? `${metrics.spread_vs_buff163_pct >= 0 ? '+' : ''}${metrics.spread_vs_buff163_pct.toFixed(2)}%`
                    : 'n/a'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </section>
  )
}
