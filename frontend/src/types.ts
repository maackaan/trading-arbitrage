export type Skin = {
  id: number
  name: string
  created_at: string
  image_url: string | null
}

export type SkinSearchResponse = {
  query: string
  corrected_query: string | null
  suggestions: string[]
  best_match: Skin | null
  wear_options: {
    wear: string
    skin: Skin
  }[]
  results: Skin[]
}

export type SkinVariantsResponse = {
  skin: Skin
  base_name: string
  wear_options: {
    wear: string
    skin: Skin
  }[]
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
  url: string | null
  spread_vs_buff163_pct: number | null
}

export type NormalizedProviderPrice = {
  item_name: string
  source: string
  price: number | null
  currency: string | null
  url: string | null
  last_updated: string
  available: boolean
  error: string | null
}

export type PriceComparison = {
  item_name: string
  sources: NormalizedProviderPrice[]
  cheapest_source: NormalizedProviderPrice | null
  percentage_difference: number | null
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
  image_url: string | null
  latest_prices: MarketSummary[]
  price_comparison: PriceComparison
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
  reference_price: number | null
  reference_market: string | null
  image_url: string | null
  price_source: string | null
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
  reference_price: number | null
  reference_market: string | null
  image_url: string | null
  price_source: string | null
  extreme_underpricing: boolean
}

export type RealtimeEvent = {
  event: 'price_update' | 'deal_alert' | 'new_listing'
  payload: Record<string, unknown>
  timestamp: string
}

export type ProviderStatus = {
  name: string
  use_mock: boolean
  supports_listings: boolean
  rate_limit_seconds: number
  last_price_error: string | null
  last_listing_error: string | null
  cooldown_until: string | null
}
