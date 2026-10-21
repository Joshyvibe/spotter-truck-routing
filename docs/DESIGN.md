# Weather-Aware Truck Routing — Plan & Design

Spotter Labs Full-Stack assessment · React + MUI · Django + DRF
Budget: 16 hours over 4 days · Guiding rule: **correctness and clarity over extra features**

---

## 0. How you're graded and what that means for the plan

| Weight | Area | What we do about it |
|---|---|---|
| 40% | Routes, weather, risk and recommendation logic | Pure, unit-tested `risk/` module. Every ambiguity in the spec is resolved explicitly and written down (section 4). |
| 40% | UI, map and heatmap smoothness and performance | MapLibre GL (WebGL), layers instead of DOM markers. The heatmap slider **never refetches**: it only changes a paint expression. |
| 15% | Code quality | Clear layers (providers → services → domain → API). Typed serializers. TypeScript on the frontend. Tests on the logic. |
| 5% | Docs and walkthrough | README + this doc + a scripted Loom (section 10). |

JD skills to show off on purpose: React + **MUI** (attention to spacing and alignment), **DRF** API design, algorithmic scoring/ranking, query/caching instincts (**Redis**), **Docker**, optionally **GCP** (Cloud Run).

---

## 1. Requirements

### Functional (MVP, all from the PDF)
1. User enters origin, destination, departure date/time, load weight (lb), and sampling interval (**10 / 25 / 50 mi**, default 25).
2. Backend gets **3 route options** from a routing API.
3. For each route, place checkpoints every N miles (the **same N for all 3 routes**, so the comparison is fair). Compute the truck's **ETA at each checkpoint**. Fetch the forecast **for that place at that ETA**.
4. Classify each checkpoint with the wind/rain/snow table **plus the load rules**.
5. Recommend one route with the 4-step ordering (severe miles → high miles → avg risk → travel time).
6. Map shows all routes, checkpoints (risk colour, ETA, details), and a summary per route.
7. Weather **heatmap over the trip corridor** with a **0–48 h slider**.

### Non-functional
- Plan response in **< 4 s** cold, **< 300 ms** warm (cached).
- Slider scrubbing at **60 fps** with no network calls.
- Works on a laptop screen and on mobile (stacked layout).
- Graceful errors: no route found, geocode miss, weather API down, departure out of forecast range.

### Out of scope (say it in the README and the Loom)
- Auth / user accounts, saved trip history UI.
- Hours-of-service (HOS) breaks in ETAs. Mention as the first "next step" since Spotter builds trucking software: insert a 30-min break after 8 h driving and a 10 h reset after 11 h.
- Real-time re-routing, traffic incidents, road closures, bridge heights.
- Building any routing engine.

---

## 2. Third-party providers (all have free tiers; check current limits when you sign up)

| Need | Choice | Why | Fallback |
|---|---|---|---|
| Geocoding / autocomplete | **TomTom Search** (fuzzy search) | Same key as routing, good US coverage | Nominatim (OSM), 1 req/s |
| Routing | **TomTom Calculate Route** with `travelMode=truck`, `vehicleWeight` (kg), `departAt`, `maxAlternatives=2`, `alternativeType=anyRoute`, `instructionsType=coded`, `routeRepresentation=polyline` | Real **truck** profile that uses the load weight. Traffic-aware ETAs at departure time. Returns 3 routes in one call. | OSRM public demo (`alternatives=3`, `annotations=duration,distance`). No truck profile, sometimes fewer than 3 routes. |
| Weather | **Open-Meteo** forecast: `hourly=wind_speed_10m,wind_gusts_10m,rain,snowfall,precipitation`, `wind_speed_unit=mph`, `precipitation_unit=inch`, `timezone=GMT`. Many coordinates in one request (comma-separated lat/lon lists). | No key, hourly, 16 days ahead, batch locations | none needed. Keep a recorded fixture for demo/tests. |
| Map tiles | MapLibre GL + free vector style (OpenFreeMap or MapTiler free key) | WebGL, smooth, no Mapbox billing | Carto raster tiles |

**Edge case: TomTom returns fewer than 3 routes** (short or very direct trips). Fill the gap by asking again with a via point offset ~10–15% of route length perpendicular to the midpoint, then drop near-duplicates (>90% shared geometry). If you still have fewer than 3, show what you have plus a clear note. Never invent a route.

Put every provider behind a small interface so the rest of the code never sees vendor JSON:

```python
class RoutingProvider(Protocol):
    def routes(self, origin: LatLng, dest: LatLng, depart_at: datetime,
               weight_lb: int) -> list[RawRoute]: ...

@dataclass(frozen=True)
class RawRoute:
    coords: list[LatLng]          # full polyline
    cum_dist_m: list[float]       # cumulative distance per coord
    cum_time_s: list[float]       # cumulative drive time per coord (from instruction offsets)
    distance_m: float
    duration_s: float
```

`cum_time_s` is the key to correct ETAs. Build it from TomTom instruction points (`routeOffsetInMeters`, `travelTimeInSeconds`) and interpolate between them. This respects slow city sections vs fast highway sections. Fall back to `distance × avg speed` only if the provider gives nothing better, and document that.

---

## 3. Architecture

```
React (Vite + TS + MUI + react-map-gl/MapLibre + TanStack Query)
        │  POST /api/plans         GET /api/plans/{id}/heatmap
        ▼
Django + DRF  ──────────────────────────────────────────────
  api/        serializers, views (thin)
  services/   plan_trip()  build_heatmap()      ← orchestration
  domain/     checkpoints.py  risk.py  ranking.py  corridor.py  ← pure, no I/O, 100% tested
  providers/  tomtom.py  osrm.py  openmeteo.py   ← HTTP, retries, timeouts
        │                     │
   Postgres (TripPlan)    Redis cache (geocode, routes, weather)
```

Use a **modular monolith**: one Django project, one app (`routing`). Microservices would be overkill and would cost hours.

### Request flow for `POST /api/plans`
1. Validate input (serializer). Geocode origin and destination (cached).
2. Get routes (cached 10 min, key = rounded coords + departure rounded to 15 min + weight bucket).
3. For each route, build checkpoints (mile 0, every N miles, and the destination) with `eta = depart_at + cum_time at that distance`.
4. **Dedup weather locations**: round every checkpoint to 0.1° (~11 km). The 3 routes overlap a lot, so this often cuts calls by 40–60%. Fetch in batches of ~50 locations, in parallel (`ThreadPoolExecutor`, 4 workers). Each location gets hourly data from `depart_at − 1h` to `max(last ETA, depart_at + 48h) + 1h`, so the heatmap can reuse it.
5. Classify each checkpoint → score each route → rank → pick the recommendation and explain it.
6. Save `TripPlan` (inputs + result JSON), return it with `id`.

The heatmap is a **separate endpoint**. The routes screen renders first (fast perceived load), and the heatmap streams in a second later.

---

## 4. Domain logic (the 40% that has to be right)

### 4.1 Checkpoints
- The user picks the interval `N ∈ {10, 25, 50}` miles (default 25). The same `N` is used for all 3 routes, and the recommendation is based on it.
- Trade-off to state in the README: a typical thunderstorm cell is ~7.5 mi across, so 10 mi catches the most weather but needs more lookups; 50 mi is fastest but can step over a storm. That is why the user gets the choice.
- Positions: `0, N, 2N, …` miles, **plus the destination** (even if the last gap is short).
- Point at distance `d`: interpolate along the polyline with `cum_dist_m`.
- ETA at `d`: `depart_at + interp(cum_dist_m, cum_time_s, d)`.
- Each checkpoint **owns the miles nearest to it** (half the gap on each side). So a route's miles split exactly into checkpoint "segments", and `Σ segment miles == route miles`. Put this invariant in a test.

### 4.2 Weather at ETA (a subtle detail worth saying in the Loom)
- **Wind** is an instantaneous value. Linearly interpolate between the two hours around the ETA.
- **Rain / snowfall** in Open-Meteo hourly data are the **sum over the previous hour**, labelled at the end of that hour. So for ETA 14:20, use the value labelled **15:00** (`ceil` to the hour). That is the in/hr rate for the hour the truck is there.
- Snowfall from Open-Meteo is snow depth. With `precipitation_unit=inch` it is in inches. Unit-test the conversion with a fixture so you are sure.
- ETA outside the forecast window → level `UNKNOWN`. Show it grey and count it separately. Never treat it as Low.

### 4.3 Classification (encode the table as data, not if-chains)

Levels: `LOW=0, MODERATE=1, HIGH=2, SEVERE=3, NO_TRAVEL=4`.

The PDF ranges touch at their edges (e.g. rain 0.10–0.25 and 0.25–0.50). Resolve them like this and write it in the README:

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | < 25 | 25 ≤ w < 35 | 35 ≤ w < 45 | 45 ≤ w < 55 | **≥ 55** |
| Rain (in/hr) | < 0.10 | 0.10 ≤ r < 0.25 | 0.25 ≤ r < 0.50 | 0.50 ≤ r ≤ 1.00 | **> 1.00** |
| Snow (in/hr) | < 0.5 | 0.5 ≤ s < 1.0 | 1.0 ≤ s < 2.0 | 2.0 ≤ s ≤ 3.0 | **> 3.0** |

Lower bounds are inclusive. The No Travel row follows the PDF exactly (`≥55` for wind, `>` for rain and snow).

```python
WIND = [(25, LOW), (35, MODERATE), (45, HIGH), (55, SEVERE)]   # value < bound → level; else NO_TRAVEL

def wind_level(mph: float, load_lb: int) -> Level:
    base = band(mph, WIND)
    if mph >= 55:                       return NO_TRAVEL                   # any load
    if 45 <= mph < 55 and load_lb > 30_000: return NO_TRAVEL
    if 35 <= mph < 45 and load_lb > 40_000: return max(base, SEVERE)
    return base

def checkpoint_level(w) -> Level:
    return max(wind_level(w.wind_mph, load), rain_level(w.rain_in), snow_level(w.snow_in))
```

Also return **the reason**: which factor drove the level (`"Wind 47 mph + 42,000 lb load → No Travel"`). Show it in the checkpoint popup. It makes the logic visible to the reviewer.

Decision to state: classify on **sustained wind** (`wind_speed_10m`), as the table says "wind". Show gusts in the popup for information only.

### 4.4 Route scoring and recommendation

Per route: `no_travel_miles, severe_miles, high_miles, moderate_miles, low_miles, unknown_miles`, `avg_risk = Σ(level × miles) / known_miles`, `duration_s`.

Ranking key (sort ascending, lexicographic):

```python
key = (
    no_travel_miles > 0,          # 0. hard gate — a route you can't legally/safely drive loses
    round(no_travel_miles, 1),
    round(severe_miles, 1),       # 1. fewest Severe miles
    round(high_miles, 1),         # 2. fewest High miles
    round(avg_risk, 2),           # 3. lowest average risk
    duration_s,                   # 4. shortest travel time
)
```

- **No Travel** is not in the PDF's preference list. It is worse than Severe, so treat it as a gate above step 1. If **every** route has No Travel miles, still rank them, but show a red banner: "No safe route at this departure time — try departing later" (the heatmap slider helps the driver pick a time).
- Rounding stops float noise (e.g. 0.0001 mi) from deciding the winner.
- Build a human explanation from the first key element that differs: *"Route B recommended: 0 severe miles vs 18 (A) and 31 (C)."* Show it on the recommended card.

### 4.5 Corridor heatmap
- Corridor = union of the 3 route lines, buffered ~40 km (`shapely`, in a projected CRS).
- Grid points inside the corridor. Choose the spacing adaptively so the count is ≤ ~400 (start at 0.25° and widen for long trips). This protects the Open-Meteo quota.
- For each point and each hour `h = 0..48` **after departure**, compute the risk level with the **same `checkpoint_level` function** (load-aware). Also keep the raw wind/precip/snow so the user can switch layers.
- Response is compact and column-shaped, not one object per point per hour:

```json
{ "start": "2026-10-21T08:00:00Z", "hours": 49,
  "points": [[lat, lon], ...],
  "risk":   [[0,1,0,...], ...],        // hours × points, uint8
  "wind":   [[12.3, ...], ...], "precip": [...], "snow": [...] }
```

400 points × 49 h × 4 layers ≈ 80k numbers, about 300–500 KB as JSON (gzip makes it small). Fetch it once and you never fetch again while scrubbing.

---

## 5. Data model

```python
class TripPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4)
    origin_text = models.CharField(max_length=255)
    destination_text = models.CharField(max_length=255)
    origin = models.JSONField()           # {lat, lng, label}
    destination = models.JSONField()
    depart_at = models.DateTimeField()    # stored UTC
    load_lb = models.PositiveIntegerField(validators=[MaxValueValidator(80_000)])
    interval_mi = models.PositiveSmallIntegerField(choices=[(10,10),(25,25),(50,50)], default=25)
    result = models.JSONField()           # routes, checkpoints, scores, recommendation
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
```

Why a JSON result instead of `Route` / `Checkpoint` tables: a plan is written once, read whole, and never queried by checkpoint. Normalising would add joins and code with no reader that needs it. **When to change:** if you need analytics like "all Severe checkpoints on I-80 last week", move checkpoints into their own table. Say this trade-off in the Loom; it shows data-model judgement.

Storing plans gives a **shareable URL** (`/plans/:id`) and the heatmap endpoint can rebuild from the stored routes.

---

## 6. API contract

### `POST /api/plans`
```json
{ "origin": "Chicago, IL", "destination": "Denver, CO",
  "depart_at": "2026-10-21T08:00:00-05:00", "load_lb": 42000, "interval_mi": 25 }
```
Accept free text **or** `{lat,lng,label}` from autocomplete.

Validation: `depart_at` must be between now − 1 h and now + 7 days (forecast reliability). `0 < load_lb ≤ 80,000`. Origin ≠ destination. Interval must be one of 10/25/50.

`201` →
```json
{ "id": "uuid", "depart_at": "...Z", "load_lb": 42000, "interval_mi": 25,
  "recommended_route_id": "r1",
  "recommendation_reason": "Fewest severe miles: 0 vs 18 (Route A) and 31 (Route C).",
  "warnings": ["Route C has 12 miles of No Travel conditions."],
  "routes": [{
    "id": "r1", "label": "Route B", "distance_mi": 1003.4, "duration_s": 54320,
    "arrive_at": "...Z", "geometry": "<encoded polyline>",
    "summary": { "no_travel_mi": 0, "severe_mi": 0, "high_mi": 22.5,
                 "moderate_mi": 80.1, "low_mi": 900.8, "unknown_mi": 0, "avg_risk": 0.21 },
    "checkpoints": [{ "mile": 25, "lat": 41.6, "lng": -88.1, "eta": "...Z",
                      "wind_mph": 18.2, "gust_mph": 29.0, "rain_in": 0.02, "snow_in": 0,
                      "level": "LOW", "segment_mi": 25, "reason": "All conditions low" }]
  }]
}
```

### `GET /api/plans/{id}` — returns the saved plan (shareable link).
### `GET /api/plans/{id}/heatmap?layer=all` — returns the column-shaped grid (section 4.5). `Cache-Control: max-age=600`.
### `GET /api/geocode?q=` — autocomplete proxy. Keeps the API key server-side. Debounce 300 ms on the client, cache 30 days on the server.

**Error contract** (one shape everywhere):
```json
{ "error": { "code": "NO_ROUTE", "message": "No truck route found between these points.", "field": null } }
```
Codes: `VALIDATION`, `GEOCODE_NOT_FOUND`, `NO_ROUTE`, `UPSTREAM_UNAVAILABLE` (502), `RATE_LIMITED` (429).

---

## 7. Frontend design (the other 40%)

### Layout (MUI)
```
┌──────────────────────── AppBar: Spotter-style title ─────────────────────┐
│ Sidebar (400px, Drawer on mobile)  │  Map (flex: 1)                      │
│ ┌ TripForm ───────────────────┐    │   routes (3 lines)                  │
│ │ Origin  (Autocomplete)      │    │   selected route: risk-coloured     │
│ │ Destination (Autocomplete)  │    │   checkpoints (circle layer)        │
│ │ Depart  (DateTimePicker)    │    │   heatmap layer (toggle)            │
│ │ Load lb (TextField + adorn) │    │                                     │
│ │ Interval ToggleButtonGroup  │    │  ┌ bottom overlay (Paper) ───────┐  │
│ │ [ Plan route ] (Loading)    │    │  │ ▶ Slider 0–48h  "Wed 14:00"  │  │
│ └─────────────────────────────┘    │  │ Layer: Risk | Wind | Precip  │  │
│ Recommendation Alert + reason      │  └───────────────────────────────┘  │
│ RouteCard ×3 (Recommended chip,    │  Legend (Low…No Travel colours)     │
│  dist, duration, arrive, risk bar) │                                     │
│ Checkpoint table (selected route)  │                                     │
└────────────────────────────────────┴─────────────────────────────────────┘
```

- One MUI theme with a fixed **risk palette**: Low green, Moderate yellow, High orange, Severe red, No Travel purple/black, Unknown grey. Use the same colours in chips, the risk bar, checkpoints, the heatmap ramp and the legend. Check contrast. Each level also gets a text label so colour is never the only signal.
- **RouteCard** shows a stacked horizontal bar of miles per level. You can compare 3 routes in one glance. Click to select; hover to highlight on the map.
- Spacing follows the theme's 8 px grid, and numbers are aligned with `tabular-nums`. The JD explicitly cares about alignment and spacing.

### Map performance rules
1. **MapLibre GL via `react-map-gl`**. WebGL rendering, not Leaflet DOM/canvas.
2. **No React markers.** Draw checkpoints as a `circle` layer on a GeoJSON source. Hundreds of points cost nothing. Use one click handler for popups.
3. Unselected routes are thin and grey. The selected route is drawn as **per-segment features coloured by level** (data-driven `line-color`). Draw the recommended one on top.
4. **Heatmap slider = zero data work.** Load the grid once into a GeoJSON source where each feature has properties `r0..r48` (and `w0..w48`, …). The slider only calls:
   ```ts
   map.setPaintProperty('heat', 'heatmap-weight', ['/', ['get', `r${hour}`], 4]);
   ```
   No re-render of React state for the map data. No `setData`. No network. Smooth at 60 fps. Throttle with `requestAnimationFrame`. Put the **slider state** in a small component so moving it does not re-render the sidebar.
5. `heatmap-radius` interpolates with zoom so the field looks continuous at every zoom. At high zoom, fade into a `circle` layer so the driver can read exact cells.
6. Memoise derived GeoJSON (`useMemo` keyed on plan id). TanStack Query caches the plan and the heatmap by id.
7. `fitBounds` to all routes after planning. Lazy-load the map bundle (`React.lazy`) so the first paint is fast.
8. **Route summaries on the map itself** (the PDF says "on a map", so don't keep them only in the sidebar). Put a small label at each route's midpoint (`symbol` layer: "B · 15h 05m · 0 severe mi"). Hovering or clicking a route line opens a popup with the full summary. Show a "Recommended" badge on the winning route's label.
9. Optional **"Show at ETA" toggle**: highlight the checkpoint markers whose ETA falls inside the slider hour. This links "where is the truck at hour X" to "what is the weather at hour X". It is cheap and makes a strong demo moment.

### State
- Server state: TanStack Query (`usePlan`, `useHeatmap`).
- UI state: `selectedRouteId`, `hoveredRouteId`, `hour`, `layer`. The interval lives in the form; changing it and planning again is fast because weather is cached. Keep it in a small context or `useReducer`; no Redux needed.
- URL: `/plans/:id` so a refresh or shared link reloads the plan.

### Frontend stack
Vite + React 18 + TypeScript, MUI v5/v6 + `@mui/x-date-pickers` (dayjs), `react-map-gl` + `maplibre-gl`, `@tanstack/react-query`, `@mapbox/polyline` to decode, Vitest + React Testing Library for a few component tests.

---

## 8. Performance, caching and failure handling

| Concern | Decision |
|---|---|
| Duplicate weather calls across 3 overlapping routes | Round to 0.1° and dedup before fetching. One batched call per ~50 locations. |
| Repeated identical plans (reviewers will click a lot) | Redis cache: geocode 30 d · routes 10 min · weather per (cell, forecast hour) 60 min. Fallback to Django's local-memory cache if `REDIS_URL` is not set. |
| Open-Meteo quota (they may count each location as a call) | Cap the heatmap grid (~400 points), widen the spacing on long trips, cache. Keep a recorded-fixture mode (`WEATHER_PROVIDER=fixture`) for tests and as an emergency demo fallback. |
| Slow upstream | `httpx` timeouts (connect 3 s, read 10 s). One retry with jitter on 5xx/timeouts only. No retry storms. |
| Upstream down | Return `UPSTREAM_UNAVAILABLE` with a clear UI message. If only the heatmap fails, routes still render and the heatmap panel shows a retry button. |
| DB | One indexed table, one read by PK. No N+1 queries anywhere. |

Rough numbers (worst case, 10 mi interval): a 1,000-mile trip = ~100 checkpoints × 3 routes = 300. After dedup ≈ 150 locations ≈ 3 batched calls. At 25 mi it is ~120 checkpoints, at 50 mi ~60. Heatmap ≈ 400 points ≈ 8 calls. Run in parallel, that is ~1–2 s cold.

---

## 9. Testing (what proves "correctness")

**Backend (pytest)** — focus here, since it is 40% of the grade:
- `risk.py`: every boundary in the table (24.99/25/34.99/35/…/55, 0.10, 0.25, 0.50, 1.00, 1.0001, snow 3.0 vs 3.01). Every load rule at 30,000 vs 30,001 and 40,000 vs 40,001 lb. Use `pytest.mark.parametrize`. Your table *is* the test table.
- `checkpoints.py`: correct positions for each of 10/25/50; the same interval is applied to all 3 routes; positions include 0 and the destination; segment miles sum to the route length; ETA interpolation is monotonic.
- Weather alignment: precip uses the hour-ending value; wind is interpolated.
- `ranking.py`: each tie-breaker level decides correctly; the No Travel gate; all-routes-unsafe banner; float noise does not flip results.
- Providers: recorded JSON fixtures (no live calls in tests); the "fewer than 3 routes" fill path.
- One API test for `POST /api/plans` with fake providers.

**Frontend:** a smoke test of the form validation, and that the RouteCard renders the recommended chip. Keep it light; the slider is better shown in the Loom.

CI: GitHub Actions running `ruff`, `pytest`, `tsc --noEmit`, `eslint`, `vitest`.

---

## 10. Repo layout, deploy, and Loom

```
spotter-truck-routing/
  backend/
    config/ (settings split: base/dev/prod)
    routing/
      api/ (serializers.py, views.py, urls.py)
      services/ (plan_trip.py, heatmap.py)
      domain/ (risk.py, checkpoints.py, ranking.py, corridor.py, types.py)
      providers/ (base.py, tomtom.py, osrm.py, openmeteo.py, fixture.py)
      tests/
    Dockerfile
  frontend/
    src/ (api/, components/{TripForm,RouteCard,RouteList,MapView,HeatmapControls,Legend}, hooks/, theme.ts, types.ts)
  docs/DESIGN.md   ← this file
  docker-compose.yml (api + postgres + redis + web)
  README.md
```

**Hosting:** pick one that **does not sleep**. A 50-second cold start ruins the reviewer's first impression.
- Backend: **Google Cloud Run** from the Dockerfile (shows the GCP + Docker bonus). Set `min-instances=1` during the review week. Alternatives: Railway or Fly.io.
- DB: Neon (free Postgres). Cache: Upstash Redis (free) or Memorystore.
- Frontend: Vercel or Netlify. Set `VITE_API_URL`. Configure CORS (`django-cors-headers`) for that origin only.
- Keep keys only on the server.

**README:** what it does, a screenshot/GIF, live link, run with `docker compose up`, env vars, **the "Decisions & assumptions" list from section 4**, providers used, known limits, next steps (HOS breaks, gust-based rules, departure-time optimiser).

**Loom (7–8 min):**
1. 0:00 Problem + live demo: Chicago → Denver, 42,000 lb, 25 mi. Point at the recommendation reason.
2. 1:30 Click checkpoints: ETA, values, reason (show a load rule firing).
3. 2:30 Scrub the heatmap slider; show it is smooth and that the "Show at ETA" markers move.
4. 3:30 Code: `risk.py` table + tests, ranking key, the precip hour-ending detail.
5. 5:00 Architecture: providers abstraction, dedup + caching, why JSON result storage.
6. 6:30 Trade-offs and what you'd do next.

Tip: choose a demo trip and date where the weather is interesting. Check a weather site the morning you record, and pick a route through a windy or stormy area so High/Severe levels actually appear.

---

## 11. 16-hour schedule (4 days)

| Day | Hours | Work | Done when |
|---|---|---|---|
| 1 | 4 | Repo, Docker compose, Django + DRF skeleton. TomTom + Open-Meteo providers with fixtures. `domain/risk.py` + `checkpoints.py` + `ranking.py` **with full tests**. | `pytest` green on all boundary tests; CLI script prints 3 scored routes for a real trip. |
| 2 | 4 | `POST /api/plans`, TripPlan model, caching, error contract. Vite + MUI + map. Form → routes on map → RouteCards → checkpoint popups. | End-to-end plan works locally. |
| 3 | 4 | Corridor grid + heatmap endpoint. Heatmap layer + slider (paint-property approach). Risk-coloured selected route, legend, hover sync, responsive layout, loading/empty/error states. | Slider is smooth on a 1,000-mile trip. |
| 4 | 4 | Deploy (Cloud Run + Vercel + Neon). CI. UI polish pass (spacing, alignment, mobile). README. Record the Loom. Buffer for surprises. | Links in the reply email. |

**Cut order if behind** (cut from the top): "Show at ETA" toggle → wind/precip layer switch (keep risk only) → shareable URL → Redis (use local-memory cache) → frontend tests. **Never cut:** the risk tests, the recommendation reason, smooth slider, the deploy.

---

## 12. Decisions and assumptions (copy into the README)

1. The user picks the sampling interval: 10, 25 or 50 miles (default 25). The same interval applies to all 3 routes, and the single recommendation is based on it. 10 mi catches small storms (~7.5 mi wide) but needs more lookups; 50 mi is faster but can miss them.
2. Checkpoints include the origin and the destination. Each checkpoint owns the miles nearest to it.
3. Overlapping table edges resolve as shown in 4.3 (lower bound inclusive; No Travel per the PDF's ≥ / >).
4. Wind = sustained 10 m wind speed. Gusts are shown, not scored.
5. Load rules only raise wind levels, never lower them. The checkpoint level is the max of wind, rain and snow.
6. No Travel miles act as a gate above "fewest Severe miles".
7. Average risk = distance-weighted mean of level index 0–4 over miles with known forecasts.
8. Precipitation for an ETA uses the hour-ending value that covers the ETA. Wind is interpolated.
9. ETAs are drive-time ETAs from the routing provider (traffic-aware at departure). They do not include HOS breaks.
10. Heatmap hours are relative to departure (hour 0 = departure time). It uses the same load-aware risk rules as the checkpoints. The PDF doesn't say whether hour 0 means "now" or "departure". Departure is more useful to the driver, but the slider label always shows the absolute date/time, so it is clear either way.
11. Forecast beyond the provider's range → `UNKNOWN`, never assumed Low.
