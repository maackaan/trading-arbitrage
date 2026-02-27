import type { DealItem, ListingItem, PricePoint, SkinSearchResponse, SkinSummary, SkinVariantsResponse } from '../types'

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }
  return (await res.json()) as T
}

export async function fetchHealth(): Promise<{
  status: string
  use_mock_providers: boolean
  mock_listings_enabled: boolean
  csfloat_listings_api_configured: boolean
  csmoney_listings_api_configured: boolean
}> {
  return getJson('/api/health')
}

export async function searchSkins(query: string): Promise<SkinSearchResponse> {
  if (!query.trim()) {
    return { query, corrected_query: null, suggestions: [], best_match: null, wear_options: [], results: [] }
  }
  const encoded = encodeURIComponent(query.trim())
  return getJson(`/api/skins/search?q=${encoded}`)
}

export async function fetchSkinSummary(skinId: number): Promise<SkinSummary> {
  return getJson(`/api/skins/${skinId}/summary`)
}

export async function fetchSkinPrices(skinId: number, range = '72h'): Promise<PricePoint[]> {
  const encodedRange = encodeURIComponent(range)
  const payload = await getJson<{ points: PricePoint[] }>(`/api/skins/${skinId}/prices?range=${encodedRange}`)
  return payload.points
}

export async function fetchSkinVariants(skinId: number): Promise<SkinVariantsResponse> {
  return getJson(`/api/skins/${skinId}/variants`)
}

export async function fetchDeals(params: { market?: string; minDiscount?: number; sinceHours?: number } = {}): Promise<DealItem[]> {
  const query = new URLSearchParams()
  if (params.market) {
    query.set('market', params.market)
  }
  if (params.minDiscount !== undefined) {
    query.set('min_discount', String(params.minDiscount))
  }
  if (params.sinceHours !== undefined) {
    query.set('since_hours', String(params.sinceHours))
  }
  return getJson(`/api/deals?${query.toString()}`)
}

export async function fetchNewListings(params: { market?: string; sinceHours?: number; limit?: number } = {}): Promise<ListingItem[]> {
  const query = new URLSearchParams()
  if (params.market) {
    query.set('market', params.market)
  }
  if (params.sinceHours !== undefined) {
    query.set('since_hours', String(params.sinceHours))
  }
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit))
  }
  return getJson(`/api/listings/new?${query.toString()}`)
}
