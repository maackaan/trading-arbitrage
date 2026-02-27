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

export function SkinDetailsPage() {
  const { skinId } = useParams<{ skinId: string }>()
  const parsedSkinId = Number(skinId)
  const [summary, setSummary] = useState<SkinSummary | null>(null)
  const [points, setPoints] = useState<PricePoint[]>([])
  const [wearOptions, setWearOptions] = useState<Array<{ wear: string; skin: Skin }>>([])
  const [loading, setLoading] = useState(false)
  const { connected, subscribe, lastEventAt } = useRealtime()

  const load = useCallback(async () => {
    if (!Number.isFinite(parsedSkinId)) return
    setLoading(true)
    try {
      const [nextSummary, nextPoints] = await Promise.all([
        fetchSkinSummary(parsedSkinId),
        fetchSkinPrices(parsedSkinId, '7d'),
      ])
      setSummary(nextSummary)
      setPoints(nextPoints)
      try {
        const variantPayload = await fetchSkinVariants(parsedSkinId)
        setWearOptions(variantPayload.wear_options)
      } catch {
        setWearOptions([])
      }
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

      <div className="grid two-col">
        <article className="card">
          <h2>Current prices</h2>
          <p>
            Buff163 baseline: <strong>{summary.baseline_price?.toFixed(2) ?? 'n/a'} USD</strong>
          </p>
          <ul className="list compact">
            {summary.latest_prices.map((price) => (
              <li key={price.market}>
                <span>{price.market}</span>
                <span>
                  {price.price.toFixed(2)} {price.currency}
                  {price.spread_vs_buff163_pct !== null
                    ? ` (${price.spread_vs_buff163_pct >= 0 ? '+' : ''}${price.spread_vs_buff163_pct.toFixed(2)}%)`
                    : ''}
                </span>
              </li>
            ))}
          </ul>
        </article>

        <article className="card">
          <h2>Prediction (+7.5 days)</h2>
          {summary.prediction_7d5 ? (
            <>
              <p>
                <strong>{summary.prediction_7d5.predicted_price.toFixed(2)} USD</strong>
              </p>
              <p className="muted">
                Band: {summary.prediction_7d5.lower_band.toFixed(2)} - {summary.prediction_7d5.upper_band.toFixed(2)} USD
              </p>
              <p className="muted">Target: {new Date(summary.prediction_7d5.target_timestamp).toLocaleString()}</p>
            </>
          ) : (
            <p className="muted">Not enough Buff163 history yet.</p>
          )}
        </article>
      </div>

      {wearOptions.length > 0 ? (
        <article className="card">
          <h2>Switch wear</h2>
          <div className="chip-row">
            {wearOptions.map((option) => (
              <Link
                key={option.skin.id}
                to={`/skins/${option.skin.id}`}
                className={`chip-link ${option.skin.id === summary.skin.id ? 'active' : ''}`}
              >
                {option.wear}
              </Link>
            ))}
          </div>
        </article>
      ) : null}

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

      <article className="card chart-card">
        <h2>Price history (7d)</h2>
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
    </section>
  )
}
