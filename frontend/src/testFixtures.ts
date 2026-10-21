import polyline from '@mapbox/polyline';

import type { Plan, Route } from './types';

const line = (lat0: number) => polyline.encode([[lat0, -100], [lat0 + 0.5, -99], [lat0 + 1, -98]], 5);

export function makeRoute(over: Partial<Route> = {}): Route {
  return {
    id: 'A',
    label: 'Route A',
    rank: 1,
    is_recommended: true,
    distance_mi: 100,
    duration_s: 6300,
    arrive_at: '2026-10-21T15:00:00Z',
    geometry: line(40),
    summary: { no_travel_mi: 0, severe_mi: 0, high_mi: 25, moderate_mi: 0, low_mi: 75, unknown_mi: 0, avg_risk: 0.5 },
    risk_segments: [
      { from_mi: 0, to_mi: 75, level: 'LOW', geometry: line(40) },
      { from_mi: 75, to_mi: 100, level: 'HIGH', geometry: line(40.5) },
    ],
    checkpoints: [
      { index: 0, kind: 'origin', mile: 0, lat: 40, lng: -100, eta: '2026-10-21T13:00:00Z', wind_mph: 10, gust_mph: 15, rain_in: 0, snow_in: 0, level: 'LOW', driver: 'none', reason: 'All conditions low', segment_mi: 50 },
      { index: 1, kind: 'destination', mile: 100, lat: 41, lng: -98, eta: '2026-10-21T15:00:00Z', wind_mph: 38, gust_mph: 50, rain_in: 0, snow_in: 0, level: 'HIGH', driver: 'wind', reason: 'Wind 38 mph → High', segment_mi: 50 },
    ],
    ...over,
  };
}

export function makePlan(): Plan {
  return {
    id: '7c1e9a2e-0000-0000-0000-000000000000',
    created_at: '2026-10-20T15:02:11Z',
    forecast_as_of: '2026-10-20T15:00:00Z',
    origin: { lat: 40, lng: -100, label: 'Origin' },
    destination: { lat: 41, lng: -98, label: 'Destination' },
    depart_at: '2026-10-21T13:00:00Z',
    load_lb: 42000,
    interval_mi: 25,
    recommended_route_id: 'A',
    recommendation_reason: 'Route A recommended for fewest severe miles: 0 vs 25 on Route B.',
    all_routes_unsafe: false,
    warnings: [],
    routes: [
      makeRoute(),
      makeRoute({ id: 'B', label: 'Route B', rank: 2, is_recommended: false, geometry: line(39) }),
    ],
  };
}
