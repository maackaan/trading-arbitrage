export type Skin = {
  id: number
  name: string
  created_at: string
}

export type SkinSearchResponse = {
  query: string
  corrected_query: string | null
  suggestions: string[]
  results: Skin[]
}

export type PricePoint = {
  market: string
  price: number
  currency: string
  timestamp: string
}

export type MarketSummary = {
  market: string
  price: number
  currency: string
  timestamp: string
  spread_vs_buff163_pct: number | null
}

export type MetricBundle = {
  mean_price: number
  rolling_mean_price: number
  spread_vs_buff163_pct: number | null
}

export type Prediction = {
  target_timestamp: string
  predicted_price: number
  lower_band: number
  upper_band: number
  model: string
}

export type SkinSummary = {
  skin: Skin
  reference_market: string
  baseline_price: number | null
  latest_prices: MarketSummary[]
  metrics_by_market: Record<string, MetricBundle>
  prediction_7d5: Prediction | null
}

export type DealItem = {
  listing_id: number
  market: string
  skin_id: number | null
  skin_name: string
  price: number
  currency: string
  listed_at: string
  detected_at: string
  discount_vs_buff_pct: number | null
  discount_vs_rolling_pct: number | null
  extreme_underpricing: boolean
}

export type ListingItem = {
  listing_id: number
  market: string
  skin_id: number | null
  skin_name: string
  price: number
  currency: string
  listed_at: string
  detected_at: string
  is_deal: boolean
  extreme_underpricing: boolean
}

export type RealtimeEvent = {
  event: 'price_update' | 'deal_alert' | 'new_listing'
  payload: Record<string, unknown>
  timestamp: string
}
