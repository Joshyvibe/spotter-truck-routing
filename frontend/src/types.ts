/** API contract types, mirroring docs/TECHNICAL_DESIGN.md §3. Units are in the field names. */

export const LEVELS = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL'] as const;
export type KnownLevel = (typeof LEVELS)[number];
export type Level = KnownLevel | 'UNKNOWN';

export interface Place {
  lat: number;
  lng: number;
  label: string;
}

export interface Checkpoint {
  index: number;
  kind: 'origin' | 'checkpoint' | 'destination';
  mile: number;
  lat: number;
  lng: number;
  eta: string;
  wind_mph: number | null;
  gust_mph: number | null;
  rain_in: number | null;
  snow_in: number | null;
  level: Level;
  driver: 'wind' | 'rain' | 'snow' | 'load' | 'none' | 'unknown';
  reason: string;
  segment_mi: number;
}

export interface RouteSummary {
  no_travel_mi: number;
  severe_mi: number;
  high_mi: number;
  moderate_mi: number;
  low_mi: number;
  unknown_mi: number;
  avg_risk: number | null;
}

export interface RiskSegment {
  from_mi: number;
  to_mi: number;
  level: Level;
  geometry: string;
}

export interface Route {
  id: string;
  label: string;
  rank: number;
  is_recommended: boolean;
  distance_mi: number;
  duration_s: number;
  arrive_at: string;
  geometry: string;
  summary: RouteSummary;
  risk_segments: RiskSegment[];
  checkpoints: Checkpoint[];
}

export interface Plan {
  id: string;
  created_at: string;
  forecast_as_of: string;
  origin: Place;
  destination: Place;
  depart_at: string;
  load_lb: number;
  interval_mi: 10 | 25 | 50;
  recommended_route_id: string;
  recommendation_reason: string;
  all_routes_unsafe: boolean;
  warnings: string[];
  routes: Route[];
}

export interface PlanRequest {
  origin: string | Place;
  destination: string | Place;
  depart_at: string;
  load_lb: number;
  interval_mi: 10 | 25 | 50;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    field: string | null;
    request_id: string | null;
    retryable: boolean;
  };
}

export const HEAT_LAYERS = ['risk', 'wind', 'precip', 'snow'] as const;
export type HeatLayer = (typeof HEAT_LAYERS)[number];

/** Column-shaped corridor grid: every layer is [hour][point]. */
export interface Heatmap {
  plan_id: string;
  start: string;
  hours: number;
  forecast_as_of: string;
  grid_step_deg: number;
  bbox: [number, number, number, number];
  points: [number, number][]; // [lat, lng]
  risk: (number | null)[][];
  wind: (number | null)[][];
  precip: (number | null)[][];
  snow: (number | null)[][];
}
