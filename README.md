# trading-arbitrage

CS2 skin price comparison and deal-detection app.

- Backend: FastAPI + SQLite + SQLAlchemy + WebSocket
- Frontend: React + TypeScript + Vite + Recharts
- Providers: pluggable adapter layer (mock mode enabled by default)

## Repository Layout

- `backend/` Python API and background refresh worker
- `frontend/` React UI
- `.env.example` shared config template

## Backend Setup (Python)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend endpoints:

- `GET /api/health`
- `GET /api/skins/search?q=`
- `GET /api/skins/{skin_id}/prices?range=72h`
- `GET /api/skins/{skin_id}/summary`
- `GET /api/deals?market=&min_discount=`
- `GET /api/listings/new?market=`
- `WS /ws`

## Frontend Setup (Node)

In another terminal from repo root:

```bash
cd frontend
npm install
npm run dev
```

Vite dev proxy forwards:

- `/api` -> `http://127.0.0.1:8000`
- `/ws` -> `ws://127.0.0.1:8000`

Open `http://localhost:5173`.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Mock vs Real Providers

By default, `USE_MOCK_PROVIDERS=true`, so markets generate sample price snapshots without API keys.
Mock listings are disabled by default (`MOCK_LISTINGS_ENABLED=false`) so Deals/New Listings never show fake rows.
`CSGOSKINS_PRICE_FALLBACK_ENABLED=false` by default to avoid csgoskins item-page rate limits.
Skin images are fetched from the csgoskins search index and cached locally at `backend/skin_images_cache.json`.
When a skin/wear is selected, backend refreshes the image from the item page and upgrades to source-resolution when available.

Adapters exist for:

- steam
- buff_market
- dmarket
- skinbaron
- buff163 (reference baseline)
- csgofloat
- skinsmonkey
- skinport
- csgofloat (new listings feed via official public API)
- csmoney (optional adapter)

When `USE_MOCK_PROVIDERS=false`, adapters intentionally return empty data until official API integrations are implemented.
No ToS-violating scraping is included.
Real CSFloat listings/deals are supported via official public API:

- `CSFLOAT_LISTINGS_API_URL` (default: `https://csfloat.com/api/v1/listings`)
- `CSGOFLOAT_API_KEY` (optional)
- `CSFLOAT_API_TIMEOUT_SECONDS` (default: `10`)
- `CSFLOAT_LISTINGS_SORT` (default: `most_recent`)
- `CSFLOAT_LISTINGS_LIMIT` (default: `50`)
- `LISTING_SINCE_HOURS` (time window filter for incoming listings)

CS.MONEY integration is still optional and requires dedicated API configuration.

## Search Behavior

- Search is fuzzy and alias-aware (e.g., `ak47`, `deagle`, `knives`, `talon`).
- Backend uses the CSGOSKINS public search index for broad catalog coverage.
- Best match returns wear variants in order: Factory New -> Minimal Wear -> Field-Tested -> Well-Worn -> Battle-Scarred.

## Prediction v1

The 7.5-day forecast is intentionally simple and replaceable:

- weighted moving average on recent Buff163 prices
- trend extrapolation from Buff163 history
- mean reversion toward cross-market anchor
- confidence band derived from recent volatility

Model implementation: `backend/app/services/prediction.py`.
