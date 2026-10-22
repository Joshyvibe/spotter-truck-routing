# Weather-Aware Truck Routing — Technical Design

Companion to [`DESIGN.md`](../DESIGN.md). Status: **draft, waiting for approval before build.**

**Sources of truth, in priority order:**
1. `fs-assessment-spotter.pdf` (the brief). It wins every conflict.
2. `DESIGN.md` (the plan). This doc follows its architecture, decisions (§12) and schedule (§11).
3. `Weather aware truck routing explained.md` (research). Used for README/Loom wording, not scope.

Anything here that is **not** already in DESIGN.md is tagged **[R#]** and listed in §8 for a yes/no. Untagged = straight from DESIGN.md or the PDF.

---

## 1. Traceability: every PDF line → where it is built

| PDF requirement | Backend | Frontend | Proved by |
|---|---|---|---|
| User enters origin & destination | `POST /plans` accepts text or `{lat,lng,label}`; `GET /geocode` | `TripForm` Autocomplete ×2 | API test + form test |
| Departure date/time | `depart_at` (ISO 8601 with offset, stored UTC) | MUI `DateTimePicker` | validation tests |
| Load weight | `load_lb` (1–80,000) feeds risk rules + truck routing | TextField with "lb" adornment | load-rule tests |
| 3 route options via routing API | `TomTomProvider` (truck mode, `maxAlternatives=2`) + via-point fill | 3 lines + 3 `RouteCard`s | provider fixture test, "<3 routes" test |
| Sample every 10 / 25 / 50 mi at the truck's ETA | `domain/checkpoints.py`, same N on all routes | `ToggleButtonGroup` 10/25/50 | position + ETA tests |
| Risk via the table + load rules | `domain/risk.py` (table as data) | level colour + text + reason in popup | parametrised boundary tests |
| Recommend best route (severe → high → avg → time) | `domain/ranking.py` lexicographic key + reason text | "Recommended" chip + reason Alert | tie-breaker tests |
| Routes, checkpoints, risk, ETAs, summaries **on a map** | `routes[].risk_segments`, `checkpoints[]`, `summary` | line + circle + symbol layers, popups, midpoint labels | Loom |
| Corridor heatmap with 0–48 h slider | `GET /plans/{id}/heatmap` (one fetch, column-shaped) | heatmap layer; slider changes a paint expression only | Loom (60 fps), no network on scrub |
| GitHub repo / hosted app / Loom | CI + Cloud Run | Vercel | links in the reply |

---

## 2. System architecture

```
                    ┌────────────── Vercel (static SPA, CDN) ──────────────┐
 Browser ──HTTPS──▶ │ React 18 + TS + MUI + react-map-gl/MapLibre + TQuery │
                    └──────────────────────────┬───────────────────────────┘
                                               │ REST/JSON (CORS: Vercel origin only)
                    ┌──────────────── Cloud Run (min-instances=0) ─────────┐
                    │ Django + DRF  (gunicorn, modular monolith, 1 app)    │
                    │  api/        serializers, views (thin), errors        │
                    │  services/   plan_trip()   build_heatmap()            │
                    │  domain/     checkpoints risk ranking corridor types  │  ← pure, no I/O
                    │  providers/  tomtom  osrm  openmeteo  fixture         │  ← HTTP, timeouts, 1 retry
                    └───────┬───────────────────┬──────────────────┬───────┘
                            │                   │                  │
                     Neon Postgres        Upstash Redis       TomTom / Open-Meteo
                     (TripPlan)           (cache + throttle)  (routing, geocode, weather)
```

Why this shape (one line each, for the Loom):
- **Modular monolith.** One request path, one deploy. Layers give the separation that microservices would, without the network hops. *Change when:* the heatmap grid needs its own scaling, then move `build_heatmap` to a worker.
- **REST/JSON.** Every call is request/response from a browser, so HTTP caching, gzip and devtools all work. No push is needed: the heatmap is one extra GET, not a stream. gRPC/GraphQL/WebSocket would be YAGNI.
- **Providers behind a Protocol.** No vendor JSON past `providers/`. Swap TomTom→OSRM or Open-Meteo→fixture with one env var.
- **Domain is pure.** All 40%-weighted logic lives in functions with no I/O, so it is tested with plain inputs and no mocks.

---

## 3. Backend API design

### 3.1 Conventions
- Base path: `/api/v1` **[R1]** (DESIGN.md uses `/api`; the `v1` prefix costs nothing and gives a clean path for breaking changes. Changes inside v1 are additive only.)
- JSON only. `snake_case`. **Units are in every field name**: `_mi`, `_s`, `_mph`, `_in`, `_lb`, `_deg`.
- All timestamps are ISO 8601 **UTC with `Z`** in responses. Requests must carry an offset; naive times are rejected (no silent timezone guess).
- Risk levels are strings: `LOW | MODERATE | HIGH | SEVERE | NO_TRAVEL | UNKNOWN`. Numeric index 0–4 is used only inside `avg_risk` and the heatmap grid.
- No auth (out of scope per DESIGN.md §1). DRF `DEFAULT_AUTHENTICATION_CLASSES = []`, so no session/CSRF on a public API.
- Gzip on (`GZipMiddleware`). Request body max 16 KB.

### 3.2 Endpoints

| Method & path | Purpose | Success | Cache |
|---|---|---|---|
| `POST /api/v1/plans` | Plan a trip: routes, checkpoints, risk, recommendation | `201` + `Location` | server-side caches only |
| `GET /api/v1/plans/{id}` | Reload a saved plan (shareable URL) | `200` | `Cache-Control: private, max-age=600` |
| `GET /api/v1/plans/{id}/heatmap` | Corridor grid, hours 0–48 from departure | `200` | `max-age=600` + `ETag` |
| `GET /api/v1/geocode?q=&limit=5` | Autocomplete proxy (keeps TomTom key server-side) | `200` | `public, max-age=86400`; Redis 30 d |
| `GET /api/v1/health` **[R2]** | Liveness for Cloud Run; no upstream calls | `200 {"status":"ok"}` | none |

No list endpoint, so **no pagination** (there is nothing to page). No `Idempotency-Key` on `POST /plans`: a retried POST only creates a second read-only plan row, and the route/weather caches make the retry cheap. It is a deliberate "not needed", which I will say in the README.

### 3.3 `POST /api/v1/plans`

Request:
```json
{
  "origin": "Chicago, IL",
  "destination": { "lat": 39.7392, "lng": -104.9903, "label": "Denver, CO" },
  "depart_at": "2026-10-21T08:00:00-05:00",
  "load_lb": 42000,
  "interval_mi": 25
}
```
`origin` / `destination`: free text (geocoded server-side) **or** an object from autocomplete (no geocode call).

Validation (all return `400 VALIDATION` with `field` set):

| Field | Rule | Why |
|---|---|---|
| `depart_at` | offset required; `now − 1 h ≤ t ≤ now + 7 d` | forecast reliability (DESIGN §6). +48 h heatmap stays inside Open-Meteo's 16-day range. |
| `load_lb` | integer, `0 < x ≤ 80,000` | DESIGN §5 |
| `interval_mi` | one of `10, 25, 50`; default `25` | PDF + DESIGN §4.1 |
| origin vs destination | must differ (< 1 km apart → error) | DESIGN §6 |
| lat/lng | `−90..90`, `−180..180`, label ≤ 255 chars | sanity |

Response `201`, header `Location: /api/v1/plans/7c1e…`:
```json
{
  "id": "7c1e9a2e-…",
  "created_at": "2026-10-20T15:02:11Z",
  "forecast_as_of": "2026-10-20T15:00:00Z",
  "origin":      { "lat": 41.8781, "lng": -87.6298, "label": "Chicago, IL" },
  "destination": { "lat": 39.7392, "lng": -104.9903, "label": "Denver, CO" },
  "depart_at": "2026-10-21T13:00:00Z",
  "load_lb": 42000,
  "interval_mi": 25,
  "recommended_route_id": "B",
  "recommendation_reason": "Route B recommended: 0 severe miles vs 18 (Route A) and 31 (Route C).",
  "all_routes_unsafe": false,
  "warnings": ["Route C has 12 miles of No Travel conditions."],
  "routes": [
    {
      "id": "B", "label": "Route B", "rank": 1, "is_recommended": true,
      "distance_mi": 1003.4, "duration_s": 54320, "arrive_at": "2026-10-22T04:05:20Z",
      "geometry": "<encoded polyline, precision 5, simplified>",
      "summary": { "no_travel_mi": 0, "severe_mi": 0, "high_mi": 22.5, "moderate_mi": 80.1,
                   "low_mi": 900.8, "unknown_mi": 0, "avg_risk": 0.21 },
      "risk_segments": [
        { "from_mi": 0, "to_mi": 412.5, "level": "LOW", "geometry": "<encoded polyline>" }
      ],
      "checkpoints": [
        { "index": 0, "kind": "origin", "mile": 0, "lat": 41.8781, "lng": -87.6298,
          "eta": "2026-10-21T13:00:00Z",
          "wind_mph": 18.2, "gust_mph": 29.0, "rain_in": 0.02, "snow_in": 0.0,
          "level": "LOW", "driver": "none", "segment_mi": 12.5,
          "reason": "All conditions low" }
      ]
    }
  ]
}
```

Notes on the shape:
- `routes[]` is sorted by `rank` (1 = recommended). Route ids/labels `A/B/C` follow the provider's order (A = TomTom's primary), so a label never changes when ranking changes. (DESIGN §6's sample has `id "r1"` with `label "Route B"`; using the letter as the id removes that mismatch.)
- `risk_segments` **[R3]**: consecutive checkpoint segments with the same level, merged, each with its own geometry. The frontend draws the risk-coloured selected route straight from this. The polyline slicing stays in tested Python, not in the browser.
- `geometry` is simplified for display (Douglas-Peucker, ~25 m tolerance) **[R4]**. Checkpoints and ETAs are computed on the **full** provider polyline. A 1,000-mile TomTom line can have 10k+ points; simplifying keeps the payload small and the map fast.
- `kind`: `origin | checkpoint | destination`. `driver`: `wind | rain | snow | load | none | unknown` (machine-readable twin of `reason`).
- `forecast_as_of` **[R5]**: the forecast snapshot time. A shared plan opened tomorrow shows "Forecast as of Tue 10:00" so nobody mistakes an old snapshot for live weather. The heatmap carries its own `forecast_as_of`.
- `segment_mi` values on a route add up to `distance_mi` (tested invariant).

### 3.4 `GET /api/v1/plans/{id}/heatmap`
```json
{
  "plan_id": "7c1e…",
  "start": "2026-10-21T13:00:00Z", "hours": 49, "forecast_as_of": "2026-10-20T15:00:00Z",
  "grid_step_deg": 0.25, "bbox": [-105.2, 38.9, -87.3, 42.4],
  "points": [[41.75, -87.5], …],
  "risk":   [[0, 1, 0, …], …],      // [hour][point], 0–4, null = UNKNOWN
  "wind":   [[12.3, …], …],          // mph, 1 decimal
  "precip": [[0.0, …], …],           // rain in/hr, 2 decimals
  "snow":   [[0.0, …], …]            // in/hr, 2 decimals
}
```
- Hour 0 = departure (DESIGN §12.10). Same load-aware `checkpoint_level()` as the routes.
- Bounded by construction: ≤ ~400 points × 49 h × 4 layers ≈ 78k numbers ≈ 300–400 KB raw, ~60–80 KB gzipped.
- Built on first request from the stored plan, then cached in Redis by `plan_id` (10 min). `?layer=` keeps DESIGN's parameter; `all` is the default and the only value the UI uses.

### 3.5 `GET /api/v1/geocode?q=chicago&limit=5`
```json
{ "data": [ { "label": "Chicago, IL, USA", "lat": 41.8781, "lng": -87.6298 } ] }
```
`q` 3–100 chars, `limit` 1–10 (default 5). TomTom fuzzy search, `countrySet=US,CA`. Key = normalised query. Client debounces 300 ms.

### 3.6 Error contract (one shape everywhere)
```json
{ "error": { "code": "NO_ROUTE", "message": "No truck route found between these points.",
             "field": null, "request_id": "req_01J…", "retryable": false } }
```
`request_id` and `retryable` are additive to DESIGN §6 **[R6]**. `request_id` is also in the `X-Request-ID` header and in every log line, so a UI error can be found in Cloud Run logs.

| Code | HTTP | Retryable | When |
|---|---|---|---|
| `VALIDATION` | 400 | no | serializer errors (`field` set) |
| `PLAN_NOT_FOUND` **[R6]** | 404 | no | unknown or malformed id |
| `GEOCODE_NOT_FOUND` | 422 | no | free text did not resolve (`field` = origin/destination) |
| `NO_ROUTE` | 422 | no | routing provider found no truck route |
| `RATE_LIMITED` | 429 + `Retry-After` | yes | our own throttle (below) |
| `UPSTREAM_UNAVAILABLE` | 502 | yes | TomTom/Open-Meteo timeout, 5xx or 429 after one retry |
| `INTERNAL` | 500 | no | unexpected; message is generic, details only in logs |

All exceptions go through one DRF `EXCEPTION_HANDLER`, so no view can return a different shape.

### 3.7 Rate limiting (protects the free-tier quotas)
DRF `ScopedRateThrottle` on the Redis cache: `plans` 20/hour/IP, `geocode` 60/min/IP, `heatmap` 60/hour/IP. 429 always sends `Retry-After`. Numbers are set from the quota maths in §3.9.

### 3.8 Service flow for `POST /plans` (DESIGN §3, with time budget)

```
validate ─▶ geocode×2 (cached 30 d) ─▶ routes (cached 10 min) ─▶ checkpoints (pure)
   ─▶ dedup weather cells ─▶ fetch missing cells (≤4 parallel batches of ~50)
   ─▶ classify ─▶ score ─▶ rank + reason ─▶ save TripPlan ─▶ 201
```
| Step | Cold | Warm |
|---|---|---|
| Geocode ×2 (parallel) | ~300 ms | ~2 ms |
| TomTom truck route, 3 alternatives | ~800–1500 ms | ~2 ms |
| Weather, ~150 cells in 3 batches, parallel | ~700–1200 ms | ~5 ms |
| Domain + DB insert | ~50 ms | ~50 ms |
| **Total** | **~2–3 s (< 4 s target)** | **< 300 ms** |

Provider details that matter for correctness:
- **TomTom** `calculateRoute`: `travelMode=truck`, `vehicleCommercial=true`, `vehicleWeight` in **kg**, `departAt` (if `depart_at` is in the past, send `now`; TomTom rejects past times), `maxAlternatives=2`, `alternativeType=anyRoute`, `instructionsType=coded`. `cum_time_s` is built from instruction `routeOffsetInMeters` + `travelTimeInSeconds`, interpolated by distance between them (DESIGN §2).
  - **`traffic=false`** (decided 2026-10-20 after measuring): live traffic only describes "now" and made long truck requests 13–31 s for near-term departures. With it off, TomTom still applies historic speeds for the departure day and time (its docs: "the effect of historic traffic on effective road speeds is still incorporated"). A 2-request check on Salt Lake City → Chicago gave the same 3 routes and a primary drive time of 19.39 h either way.
  - **8 s wall-clock deadline** on the 3-route call, one attempt, no retry. Past it, the primary route is fetched alone (~1 s) and the other options come from the "fewer than 3 routes" fill below, so no new mechanism is added. httpx's read timeout is per chunk, so it cannot catch a slowly streaming answer on its own. Worst-case cold plan ≈ 8 + 1 + 2 × 1 s.
- **Load vs vehicle weight [R7]:** the PDF's rules use **load** weight, and the risk code uses `load_lb` exactly as entered. TomTom's `vehicleWeight` means **gross** vehicle weight. I propose sending `load_lb + 35,000 lb` (typical tractor + empty 53′ trailer) converted to kg, and stating it in the README. Sending the load alone would under-weight the truck for routing.
- **Route cache key:** `round(lat,lng,3)` ×2 + `depart_at` floored to 15 min + `load` bucket of 5,000 lb (DESIGN §3).
- **Fewer than 3 routes:** via-point at ~12% of route length, perpendicular to the midpoint, both sides; drop near-duplicates (> 90% shared geometry); never invent a route; add a warning (DESIGN §2).
- **Open-Meteo:** `hourly=wind_speed_10m,wind_gusts_10m,rain,showers,snowfall`, `wind_speed_unit=mph`, `precipitation_unit=inch`, `timezone=GMT`, `timeformat=unixtime`, `past_days=1`, `forecast_days=10`, comma-separated lat/lon lists. **Decision D2 (approved 2026-10-21):** rain rate = `rain + showers`, because Open-Meteo reports convective (thunderstorm) rain in `showers`, so `rain` alone misses storms; `precipitation` is not requested. `past_days=1` keeps "depart up to 1 h ago" covered just after midnight GMT.
- **Weather cache key [R8]:** DESIGN §3 fetches a per-plan window. I propose caching the full hourly series per **cell** (0.1° for checkpoints, the fixed 0.25° lattice for the heatmap) for `forecast_days=10`, keyed `wx:{cell}:{forecast hour}`, TTL 60 min. A 10-day window covers the worst case (depart +7 d, plus a long trip, plus 48 h). Any plan crossing the same cell then hits the cache, which matters for the quota in §3.9.
- **Weather at ETA** (DESIGN §4.2): wind linearly interpolated between the two hours around the ETA; rain/snow use the **hour-ending** value of the hour the truck is in: label `floor(ETA) + 1 h`. **Decision D1 (approved 2026-10-21):** this equals DESIGN's `ceil` for every ETA except one exactly on the hour; there (e.g. the 08:00 departure checkpoint) it reads 08:00–09:00, the hour being driven, instead of 07:00–08:00, before the truck left. ETA outside the data → `UNKNOWN`. Small wording fix for the README: Open-Meteo `snowfall` is new snow over the preceding hour (not snow depth, which is a different variable), so it is already the in/hr rate the table needs.
- **HTTP:** `httpx` connect 3 s / read 10 s, one retry with jitter on timeout/5xx/429 only (none on the slow 3-route call; a TomTom 4xx/5xx there costs one request, not two). `httpx`/`httpcore` loggers are kept at WARNING because they log full URLs, and TomTom's key is a query parameter.

### 3.9 Numbers (back-of-the-envelope)

| Quantity | Value | Consequence |
|---|---|---|
| Checkpoints, 1,000-mi trip, 3 routes | ~303 / 123 / 63 at 10 / 25 / 50 mi | after 0.1° dedup ≈ 150 / 80 / 50 weather cells |
| Heatmap grid | ≤ 400 points | adaptive spacing, starting at 0.25° |
| Open-Meteo cost of one cold plan + heatmap | ~450–550 location-calls (Open-Meteo counts each location) | free tier ≈ 10k/day → ~20 fully-cold plans/day. Cell caching + fixed lattice make repeat/nearby plans close to free. Fixture mode is the emergency fallback. **Verify current limits at signup.** |
| TomTom per plan | 1 routing call (+ up to 2 fill-ins) + ≤ 2 geocodes | free tier ~2,500/day, not the bottleneck |
| Plan response size | ~60–100 KB raw, ~20 KB gzipped | one round trip |
| Heatmap response | ~300–400 KB raw, ~60–80 KB gzipped | fetched once per plan |

### 3.10 Data model
`TripPlan` exactly as DESIGN §5, plus `forecast_as_of` (DateTime) for [R5]. Result stored as JSON: written once, read whole, never queried by checkpoint. *Change when:* we need analytics across checkpoints. One indexed table, reads by PK only, no N+1.

### 3.11 Settings, logging, quality
- `config/settings/{base,dev,prod}.py`. All secrets from env. `CACHES` uses Redis when `REDIS_URL` is set, else local-memory (DESIGN §8).
- Providers chosen by env: `ROUTING_PROVIDER=tomtom|osrm`, `WEATHER_PROVIDER=openmeteo|fixture`.
- Structured JSON logs: `request_id`, endpoint, status, total ms, and ms per provider call, plus cache hit/miss. That is enough observability for this scope. No APM.
- `ruff` + `mypy` (on `domain/` at least) + `pytest`. Tests as DESIGN §9.

---

## 4. Frontend design

### 4.1 Stack (DESIGN §7)
Vite + React 18 + TypeScript (strict), MUI v6 + `@mui/x-date-pickers` (dayjs), `react-map-gl/maplibre` + `maplibre-gl`, `@tanstack/react-query`, `react-router` (two routes), `@mapbox/polyline`. Tiles: OpenFreeMap vector style (no key). Tests: Vitest + React Testing Library. Lint: ESLint + `tsc --noEmit`.

### 4.2 Routes
- `/` empty map + form.
- `/plans/:id` loads the plan by id. A refresh or a shared link restores everything.

### 4.3 Component tree
```
App (ThemeProvider, QueryClientProvider, LocalizationProvider, Router)
└─ PlannerPage
   ├─ AppBar
   ├─ Sidebar (400 px; bottom sheet/Drawer on mobile)
   │   ├─ TripForm            origin/destination Autocomplete (useGeocode, 300 ms debounce),
   │   │                      DateTimePicker, load TextField ("lb"), interval ToggleButtonGroup, submit (loading)
   │   ├─ RecommendationAlert reason text; red "No safe route at this departure time" banner when all_routes_unsafe
   │   ├─ RouteList → RouteCard ×3   Recommended chip, distance, duration, arrive, stacked risk-miles bar
   │   └─ CheckpointTable     selected route: mile, ETA, level chip, wind/rain/snow, reason
   └─ MapView (React.lazy)
       ├─ sources/layers: routes-base, route-risk-selected, checkpoints, route-labels, heat, heat-cells
       ├─ Popups (one click handler per layer)
       ├─ HeatmapControls     ▶ play, slider 0–48, absolute time label, layer switch Risk|Wind|Precip|Snow, "Show at ETA"
       └─ Legend              Low … No Travel, Unknown
```

### 4.4 State
- **Warm-up:** `App` fires one `GET /api/v1/health` on mount (fire-and-forget) so a scaled-to-zero Cloud Run instance starts while the user types.
- **Server state:** TanStack Query. `useCreatePlan` (mutation → navigate to `/plans/:id` and seed the cache), `usePlan(id)`, `useHeatmap(id)` (starts as soon as the plan exists, so routes render first), `useGeocode(q)`. `staleTime` 10 min to match server caching.
- **UI state:** `selectedRouteId`, `hoveredRouteId` in a small context with `useReducer`. Default selection = recommended route.
- **Slider state:** local to `HeatmapControls`. Moving the slider does **not** re-render the sidebar or MapView.

### 4.5 Map performance rules (the 40% UI grade)
1. WebGL layers only. No React markers. Checkpoints are one `circle` layer on one GeoJSON source.
2. Unselected routes: thin grey. Selected route: `risk_segments` with data-driven `line-color`. Recommended route drawn on top. Hover = thicker line via `feature-state` (no `setData`).
3. **Slider = zero data work.** The heatmap grid becomes one GeoJSON source once (`useMemo` on plan id). Each point has properties `r0…r48`, `w0…w48`, `p0…p48`, `s0…s48`. Moving the slider calls only `map.setPaintProperty('heat', 'heatmap-weight', ['/', ['coalesce', ['get', 'r'+h], 0], 4])`, throttled with `requestAnimationFrame`. No React re-render of map data, no `setData`, no network.
4. `heatmap-radius` interpolates with zoom; at high zoom it fades into a `circle` layer (`heat-cells`) coloured by level, so exact cells can be read.
5. Route summaries **on the map**: `symbol` layer at each route midpoint ("B · 15h 05m · 0 severe mi", with a Recommended badge). Click a line for the full summary popup.
6. "Show at ETA": each checkpoint carries `eta_hour` (hours after departure, computed once on load). The slider updates a `circle-opacity`/`circle-stroke-width` expression to light up checkpoints in the current hour. Same paint-only technique.
7. `fitBounds` to all routes after planning, with padding for the sidebar.
8. Map bundle lazy-loaded, so the form paints first.

### 4.6 Design system
- One MUI theme. 8 px spacing grid. `font-variant-numeric: tabular-nums` on every number column.
- One risk palette shared by chips, risk bar, route segments, checkpoints, heatmap ramp and legend: Low green, Moderate yellow, High orange, Severe red, No Travel purple-black, Unknown grey. Each level also shows a **text label**, so colour is never the only signal. Contrast checked for chip text.
- Times shown in the **browser's timezone with the abbreviation** ("Wed 14:00 CDT"). The departure picker uses the same timezone and sends an ISO string with offset. (Showing times in the origin's local timezone is a next step.)

### 4.7 UI states
- Loading: button spinner, skeleton RouteCards, routes appear before the heatmap.
- Errors: the API `error.code` maps to a friendly message. `field` errors show under the matching input. `UPSTREAM_UNAVAILABLE` gets a Retry button. Heatmap failure leaves routes working and shows a retry in the heatmap panel (DESIGN §8).
- Empty: helpful starter text on the empty map.
- Mobile: map on top, sidebar as a bottom sheet. Slider stays reachable.

### 4.8 Frontend tests (kept light, as DESIGN §9)
Form validation, the RouteCard Recommended chip, error-code → message mapping, and the heatmap property builder (`grid → GeoJSON`, pure function).

---

## 5. Deployment design

> **Superseded by D8 (§9, 2026-10-22):** the API is hosted on **Northflank** (free, always-on Developer Sandbox) instead of Cloud Run. The rest of this section (Vercel, Neon, Upstash, secrets kept out of the browser, CORS, migrations at start-up) still applies; the Cloud Run, Artifact Registry and deploy-workflow details below are historical.

```
GitHub (main) ──▶ GitHub Actions
                   ├─ backend: ruff · mypy · pytest ─▶ docker build ─▶ Artifact Registry ─▶ Cloud Run deploy
                   └─ frontend: eslint · tsc · vitest ─▶ (Vercel builds from Git on its own)

Vercel (SPA, CDN) ──HTTPS──▶ Cloud Run (us-east4, min-instances=0, 1 vCPU / 512 MB, concurrency 20)
                                 ├─▶ Neon Postgres (pooled endpoint, sslmode=require, nearby AWS us-east region)
                                 ├─▶ Upstash Redis (TLS, same region family)
                                 └─▶ TomTom · Open-Meteo
```

| Piece | Decision | Why |
|---|---|---|
| Backend | Cloud Run from the Dockerfile, `min-instances=0` (free tier). The SPA calls `GET /api/v1/health` on page load as a warm-up | A cold start takes a few seconds and happens while the reviewer fills in the form, so the first plan meets a warm instance. Shows GCP + Docker. *Change when:* the warm-up is not enough, then set `min-instances=1` for review week. |
| Container | `python:3.12-slim`, non-root user, gunicorn `--workers 2 --threads 4 --timeout 30` | Threads suit I/O-bound upstream calls. |
| Migrations | Entrypoint runs `migrate --noinput` before gunicorn | One table, one instance: simplest safe option. *Change when:* several instances or risky migrations, then use a Cloud Run Job. |
| Secrets | Secret Manager → env (`TOMTOM_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `DJANGO_SECRET_KEY`) | Keys never reach the browser. |
| DB / cache | Production only: Neon free Postgres (stores `TripPlan`); Upstash free Redis (caches + throttle counters). Dev uses the Postgres and Redis containers from `docker compose` | Free, managed, no sleep. A shared cache survives Cloud Run scaling to zero, so warm plans stay fast and the Open-Meteo quota is protected. |
| Frontend | Vercel, `VITE_API_URL`, `vercel.json` rewrite of all paths to `index.html` | Needed so `/plans/:id` works on refresh. |
| CORS | `django-cors-headers`, only the Vercel production origin (plus localhost in dev) | |
| Security headers | `SECURE_PROXY_SSL_HEADER`, HSTS, `ALLOWED_HOSTS` = Cloud Run host, `DEBUG=False` | |
| Local dev | `docker compose up`: `api`, `postgres`, `redis`, `web` (Vite) | DESIGN §10 |
| Cost | $0: everything is on free tiers. A $1 budget alert is set on the GCP billing account | Billing must be enabled for Cloud Run, but usage stays inside the free allowance. |

Environment variables:

| Var | Where | Example |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | api | `config.settings.prod` |
| `DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `TOMTOM_API_KEY` | api (secrets) | — |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | api | Cloud Run host / Vercel URL |
| `ROUTING_PROVIDER`, `WEATHER_PROVIDER` | api | `tomtom`, `openmeteo` |
| `VITE_API_URL`, `VITE_MAP_STYLE_URL` | web | Cloud Run URL / OpenFreeMap style |

---

## 6. Repository layout (DESIGN §10)
```
spotter-truck-routing/
  backend/
    config/settings/{base,dev,prod}.py  urls.py  wsgi.py
    routing/
      api/        serializers.py views.py urls.py errors.py throttles.py
      services/   plan_trip.py heatmap.py
      domain/     types.py risk.py checkpoints.py ranking.py corridor.py weather_at_eta.py
      providers/  base.py tomtom.py osrm.py openmeteo.py fixture.py http.py
      models.py migrations/
      tests/      domain/ providers/ api/ fixtures/
    Dockerfile  entrypoint.sh  pyproject.toml
  frontend/
    src/ api/ components/ hooks/ theme.ts types.ts   (DESIGN §10; the risk palette lives in theme.ts)
    vercel.json
  docs/  DESIGN.md  TECHNICAL_DESIGN.md  research/weather-aware-truck-routing.md
  .github/workflows/ci.yml
  docker-compose.yml  README.md
```
(`DESIGN.md` and the research note move into `docs/` when we scaffold, matching DESIGN §10.)

---

## 7. Build order (unchanged from DESIGN §11)
Day 1 domain + providers + full boundary tests · Day 2 API + model + caching + basic UI · Day 3 heatmap end to end + polish states · Day 4 deploy, CI, README, Loom. Cut order and the "never cut" list stay as in DESIGN §11.

---

## 8. Refinements that need your yes/no

All are small, and each one supports a PDF line or a grading line. Saying no to any of them leaves DESIGN.md exactly as written.

| # | Refinement | Supports |
|---|---|---|
| R1 | `/api/v1` prefix instead of `/api` | Code quality: versioning story |
| R2 | `GET /api/v1/health` | Deploy: Cloud Run health check |
| R3 | `risk_segments` (merged, with geometry) in each route | "risk levels on a map", map performance |
| R4 | Simplified display geometry (math stays on the full line) | Map smoothness, payload size |
| R5 | `forecast_as_of` on plan and heatmap | Correctness when an old shared plan is opened |
| R6 | `request_id` + `retryable` in the error envelope; `PLAN_NOT_FOUND` code | Error contract completeness |
| R7 | Send TomTom gross weight = `load_lb + 35,000 lb`; risk rules use load as entered | Correct truck routing; PDF rules unchanged |
| R8 | Weather cached per cell for a fixed 10-day window; fixed 0.25° heatmap lattice | Open-Meteo quota; warm plans < 300 ms |

Before build day I will also need from you: a TomTom API key (have it), and accounts for GCP (billing enabled for Cloud Run, $1 budget alert), Neon, Upstash, Vercel and GitHub. The folder is not a git repo yet; I will `git init` when we scaffold.

---

## 9. Decisions and implementation details recorded after approval (2026-10-21 scope review)

A full review against the PDF, DESIGN.md and this document reverted every unapproved addition. What remains beyond the text above is listed here, so the code holds nothing undocumented.

**Approved decisions**
- **D1** Rain/snow at an ETA exactly on the hour use the hour being driven (§3.8).
- **D2** Rain rate = `rain + showers` (§3.8).
- **D3** `WEATHER_PROVIDER=fixture` replays a **recorded real** Open-Meteo snapshot (DESIGN §2/§8 "recorded fixture"). It is a 2° grid over the contiguous US (390 points, 1 past + 3 forecast days, `backend/routing/providers/fixtures/openmeteo_us_grid.json.gz`, ~97 KB), recorded with `manage.py record_weather_fixture`. Each point reads its nearest grid cell, and the recording is re-timed to start one day before the current hour; hours past the window are `UNKNOWN`.
- **D4** TomTom `traffic=false` (historic speeds for the departure day/time) plus an 8 s deadline on the 3-route call, falling back to the "fewer than 3 routes" fill (§3.8).
- **D5** UI per the docs: "Show at ETA" is a toggle, **on by default** (changed back on request, 2026-10-21); the checkpoint table has a Reason column (it scrolls sideways in the 400 px sidebar); on mobile the sidebar is a bottom Drawer opened from the app bar; folder layout as DESIGN §10, with a `RouteList` component.

**Implementation details that make documented features work**
- Cache keys include the provider name (fixture and real data can never mix), and the heatmap key includes the forecast hour (so a new forecast rebuilds it). The geocode key includes `limit` (free-text resolve uses 1 result, autocomplete 5).
- Error codes `NOT_FOUND` (unknown URL) and `METHOD_NOT_ALLOWED` keep the one error envelope on every response. A TomTom 4xx other than "no route" (bad key, quota) is `INTERNAL`, not retryable. A geocode query with no match returns `200 {"data": []}`. The frontend uses `NETWORK` for an unreachable server.
- Offline `ROUTING_PROVIDER=fixture` (three bowed lines, five cities) gives the API tests their fake providers (DESIGN §9). Without a TomTom key, geocoding falls back to Nominatim (DESIGN §2), which is spaced to 1 request/s.
- A plan whose routes have miles with no forecast gets a warning (DESIGN §4.2 "count separately"). With no known miles, `avg_risk` is `null` and ranks last.
- **D8 (approved 2026-10-21, updated 2026-10-22)** Hosting: the **API on Northflank** (free Developer Sandbox, always on, US - Central), built from `backend/Dockerfile` with build context `/backend`; port 8080 public; no HTTP health check (Northflank's HTTP probe sends the container IP as host, which `ALLOWED_HOSTS` rejects). GCP's Free Trial needed a prepayment and Railway's checkout was down, so Northflank replaced both. The frontend is on Vercel; Postgres on Neon and Redis on Upstash are unchanged. The host deploys from GitHub itself, so there is no deploy workflow. Live: API https://p01--spotter-truck-routing--8zfwjn862f7f.code.run, app https://spotter-truck-routing-omega.vercel.app.
- **D7 (approved 2026-10-21)** Ranking puts **fewest miles without a forecast** right after the No Travel gate, before the brief's order. UNKNOWN is never treated as Low (DESIGN §4.2), so a route that cannot be checked never beats one that can. With live data this only matters past the 10-day forecast range.
- **D6 (approved 2026-10-21)** "Show at ETA" shows **one truck icon per route** at the truck's position at the slider's hour, placed along the road from the checkpoint ETAs (time → mile → point; after arrival it waits at the destination), plus rings on the checkpoints reached in that hour. Positions for all 49 hours are built once per plan; the slider only calls `setFilter` on the truck and ring layers (no data reload, no network). Filters are expression filters, and a test compiles them with MapLibre's own filter compiler.
- The Wind/Precip/Snow heatmap layers colour the raw values with the brief's bands, so every layer shares one colour scale.
- Slider: hour marks at 0/12/24/36/48, an absolute time label plus "+N h after departure", a one-line note per layer, and play at 450 ms per hour, stopping at 48 h. The form shows the interval trade-off text from DESIGN §4.1. The app bar has "New trip".
- Runtime plumbing: `backend/.env` is loaded for local runs (`config/env.py`); `PORT` is set by Cloud Run; `VITE_PROXY_TARGET` points the dev proxy at the `api` container; CORS exposes `X-Request-ID`, `Retry-After` and `Location`; TomTom search uses `typeahead=true` and `idxSet=Geo,PAD,Addr,Str` for place-name autocomplete.

