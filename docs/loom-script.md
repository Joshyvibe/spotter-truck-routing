# Loom walkthrough script (7–8 min)

Follows the outline in DESIGN.md §10. Times are targets. Speak to the reviewer's grading split: 40% logic, 40% UI smoothness, 15% code, 5% docs.

## Before you record

- **Pick a trip with interesting weather.** On the morning you record, look at a US weather map, for example NWS high-wind or winter-storm warnings, and choose a trip through that area. Good candidates: I-80 across Wyoming (wind), I-70 over Colorado (snow), I-90/I-94 in the Upper Midwest (winter storms). When the recording was made (2026-10-21) the forecast was calm over land, and the only High-or-worse weather was offshore east of New England.
- Use **42,000 lb**, so the "35–44 mph + >40,000 lb → Severe" load rule can fire.
- Plan the trip once before recording, so it's cached and loads instantly on camera.
- Open three tabs: the app, `backend/routing/domain/risk.py`, and `backend/routing/domain/ranking.py`.
- Fallback if every route is all Low: say so plainly. It shows the app never invents risk. Then show `test_risk.py` running for the risk logic.

## 0:00 – 1:30 · Problem and live demo

- "Normal GPS picks roads. This app asks *what will the weather be where this truck is, when it gets there*, and picks the safest of 3 truck routes."
- Fill in the form: origin, destination, departure, 42,000 lb, 25 mi. Mention the 10/25/50 trade-off shown under the toggle.
- Click **Plan route**. Point at:
  - the 3 routes on the map with their labels, e.g. "B · 15h 05m · 0 severe mi · Recommended";
  - the **recommendation reason**, e.g. "Route B recommended: 0 severe miles vs 18 (A) and 31 (C).";
  - the route cards: miles per risk level in the stacked bar, drive time, arrival.

## 1:30 – 2:30 · Checkpoints, ETAs, load rules

- Click a checkpoint on the map. Show its ETA, wind (sustained; gusts shown but not scored), rain, snow, and the **reason**.
- If one fires, point out a load rule, e.g. "Wind 38 mph + 42,000 lb load → Severe". Otherwise change the load and re-plan to show the level change.
- Open the checkpoint table (it has a Reason column) and click a row: the map opens that checkpoint.
- Mention: "Each checkpoint owns the miles nearest to it, so a route's miles add up exactly to its length."

## 2:30 – 3:30 · Heatmap and slider (the smoothness grade)

- Scrub the **0–48 h slider**. "The grid is fetched once. Scrubbing only swaps a paint expression: no network, no re-render. On the production build that's 60 fps."
- Switch **Risk / Wind / Precip / Snow**. Risk is load-aware, using the same rules as the checkpoints.
- Turn on **Show at ETA**: the rings show where each truck is at that hour, next to the weather at that hour.
- Optional: open devtools → Network while scrubbing to show zero requests.

## 3:30 – 5:00 · Code: the 40% that must be right

- `risk.py`: the brief's table **as data** (bands + load rules), not if-chains. Edge rule: lower bounds inclusive, No Travel exactly as the PDF (≥ 55 mph, > 1.00, > 3.0).
- `test_risk.py`: every boundary is a parametrised test: 24.99 / 25 mph, 30,000 / 30,001 lb, 1.00 / 1.0001 in/hr.
- `ranking.py`: the lexicographic sort key. No Travel is a gate above Severe; rounding stops float noise from picking the winner; the reason comes from the first rule that separates the winner from the runner-up.
- `weather_at_eta.py`: wind is interpolated, but Open-Meteo rain/snow are **hour-ending totals**, so 14:20 reads the 15:00 value. Rain = rain + showers, because thunderstorm rain is reported separately.

## 5:00 – 6:30 · Architecture and trade-offs

- A modular monolith: `providers/` (vendor JSON stops here), `services/` (I/O, caching), `domain/` (pure, fully tested), `api/` (thin views, one error envelope).
- Weather: 3 routes overlap, so checkpoints are snapped to 0.1° cells and de-duplicated, fetched in parallel batches, and cached per cell for 60 min. The heatmap grid sits on a fixed lattice, so nearby plans share the cache.
- TomTom: truck profile with the gross weight, historic speeds for the departure time, and an 8 s deadline with a fallback for the slow alternatives call.
- Plans are stored as one JSON result: written once, read whole, never queried by checkpoint. "When analytics are needed, checkpoints move to their own table."
- Hosting: the same Docker image runs on Railway (API) behind Vercel (frontend), with Neon Postgres and Upstash Redis; CI runs every check on each push.

## 6:30 – 7:30 · Limits and next steps

- The brief's load rules raise risk for heavier loads; real crosswind closures target **lighter** high-profile trucks. Implemented as written, and flagged.
- Next: hours-of-service breaks in ETAs, gust-based and light-truck wind rules, and a departure-time optimiser that scans the next 48 h for the safest window.
- Close: "Correctness and clarity first: every rule is visible in the UI, written down in the README, and covered by a test."
