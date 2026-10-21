/** Pure builders from the API plan to GeoJSON for MapLibre sources (tested, memoised by plan id). */
import polyline from '@mapbox/polyline';
import type { Feature, FeatureCollection, LineString, Point } from 'geojson';

import type { Plan } from '../types';

export type LngLat = [number, number];

export function decode(encoded: string): LngLat[] {
  // polyline gives [lat, lng]; GeoJSON wants [lng, lat].
  return polyline.decode(encoded, 5).map(([lat, lng]) => [lng, lat]);
}

export function routeLines(plan: Plan): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: plan.routes.map((r) => ({
      type: 'Feature',
      id: r.rank,
      properties: { routeId: r.id, recommended: r.is_recommended, rank: r.rank },
      geometry: { type: 'LineString', coordinates: decode(r.geometry) },
    })),
  };
}

export function riskSegments(plan: Plan): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: plan.routes.flatMap((r) =>
      r.risk_segments.map((s) => ({
        type: 'Feature' as const,
        properties: { routeId: r.id, level: s.level, from_mi: s.from_mi, to_mi: s.to_mi },
        geometry: { type: 'LineString' as const, coordinates: decode(s.geometry) },
      })),
    ),
  };
}

export function checkpointPoints(plan: Plan): FeatureCollection<Point> {
  const departMs = Date.parse(plan.depart_at);
  return {
    type: 'FeatureCollection',
    features: plan.routes.flatMap((r) =>
      r.checkpoints.map(
        (c): Feature<Point> => ({
          type: 'Feature',
          properties: {
            routeId: r.id,
            index: c.index,
            level: c.level,
            kind: c.kind,
            // hours after departure, for the "show at ETA" slider highlight
            etaHour: Math.floor((Date.parse(c.eta) - departMs) / 3_600_000),
          },
          geometry: { type: 'Point', coordinates: [c.lng, c.lat] },
        }),
      ),
    ),
  };
}

/** One label per route at its midpoint: "B · 15h 05m · 0 severe mi". */
export function routeLabels(
  plan: Plan,
  text: (routeId: string) => string,
): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: plan.routes.map((r) => {
      const coords = decode(r.geometry);
      const at = coords[Math.floor(coords.length / 2)] ?? coords[0]!; // midpoint (DESIGN §7.8)
      return {
        type: 'Feature',
        properties: { routeId: r.id, text: text(r.id), recommended: r.is_recommended },
        geometry: { type: 'Point', coordinates: at },
      };
    }),
  };
}

export function bounds(plan: Plan): [LngLat, LngLat] {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const r of plan.routes) {
    for (const [x, y] of decode(r.geometry)) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  return [[minX, minY], [maxX, maxY]];
}

/** Hours on the forecast slider: 0..48 after departure. */
export const SLIDER_HOURS = 49;

const EARTH_RADIUS_MI = 3958.8;

function haversineMi([lng1, lat1]: LngLat, [lng2, lat2]: LngLat): number {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLng = (lng2 - lng1) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.sqrt(h));
}

/** Piecewise-linear interpolation over ascending xs, clamped at the ends. */
function interp(xs: number[], ys: number[], x: number): number {
  if (x <= xs[0]!) return ys[0]!;
  const last = xs.length - 1;
  if (x >= xs[last]!) return ys[last]!;
  let i = 1;
  while (xs[i]! < x) i++;
  const x0 = xs[i - 1]!, x1 = xs[i]!;
  return x1 === x0 ? ys[i]! : ys[i - 1]! + ((ys[i]! - ys[i - 1]!) * (x - x0)) / (x1 - x0);
}

/** The point at a given mile along a line, measured as a share of the route's length. */
function pointAtMile(coords: LngLat[], mile: number, totalMi: number): LngLat {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) cum.push(cum[i - 1]! + haversineMi(coords[i - 1]!, coords[i]!));
  // The display line is simplified, so scale its length to the route's real distance.
  const target = (mile / totalMi) * cum[cum.length - 1]!;
  return [interp(cum, coords.map((c) => c[0]), target), interp(cum, coords.map((c) => c[1]), target)];
}

/**
 * One truck per route per slider hour: where the truck is at departure + h hours, placed
 * along the road from the checkpoint ETAs (time -> mile -> point). Built once per plan; the
 * slider only changes the layer filter. After arrival the truck waits at the destination.
 */
export function truckPositions(plan: Plan): FeatureCollection<Point> {
  const departMs = Date.parse(plan.depart_at);
  return {
    type: 'FeatureCollection',
    features: plan.routes.flatMap((r) => {
      const coords = decode(r.geometry);
      const times = r.checkpoints.map((c) => Date.parse(c.eta));
      const miles = r.checkpoints.map((c) => c.mile);
      const arriveMs = times[times.length - 1]!;
      return Array.from({ length: SLIDER_HOURS }, (_, hour): Feature<Point> => {
        const t = departMs + hour * 3_600_000;
        const mile = interp(times, miles, t);
        return {
          type: 'Feature',
          properties: { routeId: r.id, hour, recommended: r.is_recommended, arrived: t >= arriveMs },
          geometry: { type: 'Point', coordinates: pointAtMile(coords, mile, r.distance_mi) },
        };
      });
    }),
  };
}
