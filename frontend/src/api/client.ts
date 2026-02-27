import type { DealItem, ListingItem, PricePoint, SkinSearchResponse, SkinSummary } from '../types'

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }
  return (await res.json()) as T
}

export async function fetchHealth(): Promise<{ status: string; use_mock_providers: boolean }> {
  return getJson('/api/health')
}

export async function searchSkins(query: string): Promise<SkinSearchResponse> {
  if (!query.trim()) {
    return { query, corrected_query: null, suggestions: [], results: [] }
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

export async function fetchDeals(params: { market?: string; minDiscount?: number } = {}): Promise<DealItem[]> {
  const query = new URLSearchParams()
  if (params.market) {
    query.set('market', params.market)
  }
  if (params.minDiscount !== undefined) {
    query.set('min_discount', String(params.minDiscount))
  }
  return getJson(`/api/deals?${query.toString()}`)
}

export async function fetchNewListings(params: { market?: string } = {}): Promise<ListingItem[]> {
  const query = new URLSearchParams()
  if (params.market) {
    query.set('market', params.market)
  }
  return getJson(`/api/listings/new?${query.toString()}`)
}
