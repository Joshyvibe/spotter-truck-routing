/**
 * Heatmap source + paint expressions. The slider never touches data: the grid becomes one
 * GeoJSON source once, with properties r0..r48 / w0..w48 / p0..p48 / s0..s48 per point, and
 * moving the slider only swaps which property the paint expressions read.
 */
import type { ExpressionSpecification, FilterSpecification } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';

import { RISK } from '../theme';
import type { HeatLayer, Heatmap } from '../types';

const PREFIX: Record<HeatLayer, string> = { risk: 'r', wind: 'w', precip: 'p', snow: 's' };

/**
 * Raw layers are classified with the brief's own bands (lower bound inclusive, No Travel per
 * the table's >= / >), so every layer shares one colour scale with the same meaning.
 * Only the Risk layer (computed server-side) includes the load rules and the max of factors.
 */
const BANDS: Record<Exclude<HeatLayer, 'risk'>, number[]> = {
  wind: [25, 35, 45, 55], // >= 55 -> No Travel
  precip: [0.1, 0.25, 0.5, 1.0 + 1e-9], // > 1.00 -> No Travel
  snow: [0.5, 1.0, 2.0, 3.0 + 1e-9], // > 3.0 -> No Travel
};

export const LAYER_INFO: Record<HeatLayer, { label: string; note: string }> = {
  risk: { label: 'Risk', note: 'Load-aware risk: the same rules as the checkpoints' },
  wind: { label: 'Wind', note: 'Sustained wind by the table bands (load rules not applied)' },
  precip: { label: 'Precip', note: 'Rain rate by the table bands' },
  snow: { label: 'Snow', note: 'Snowfall rate by the table bands' },
};

export function heatmapSource(h: Heatmap): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: h.points.map(([lat, lng], i) => {
      const props: Record<string, number> = {};
      for (const layer of Object.keys(PREFIX) as HeatLayer[]) {
        const rows = h[layer];
        for (let hour = 0; hour < h.hours; hour++) {
          const v = rows[hour]?.[i];
          // Missing values stay absent; expressions coalesce them to "no colour".
          if (v !== null && v !== undefined) props[`${PREFIX[layer]}${hour}`] = v;
        }
      }
      return { type: 'Feature', properties: props, geometry: { type: 'Point', coordinates: [lng, lat] } };
    }),
  };
}

const prop = (layer: HeatLayer, hour: number) => `${PREFIX[layer]}${hour}`;

/** Level 0..4 for a cell at an hour; -1 when the forecast does not cover it. */
export function levelExpression(layer: HeatLayer, hour: number): ExpressionSpecification {
  const key = prop(layer, hour);
  const value: ExpressionSpecification = ['get', key];
  const level: ExpressionSpecification =
    layer === 'risk'
      ? value
      : ['step', value, 0, ...BANDS[layer].flatMap((b, i) => [b, i + 1])] as unknown as ExpressionSpecification;
  return ['case', ['has', key], level, -1];
}

/** Heat weight: level / 4, so Low and unknown add no colour. */
export function weightExpression(layer: HeatLayer, hour: number): ExpressionSpecification {
  return ['/', ['max', 0, levelExpression(layer, hour)], 4];
}

/** Density ramp in the shared risk palette. Low stays transparent so the base map reads. */
export const HEAT_COLOR: ExpressionSpecification = [
  'interpolate', ['linear'], ['heatmap-density'],
  0, 'rgba(0,0,0,0)',
  0.12, hexA(RISK.MODERATE.color, 0.45),
  0.37, hexA(RISK.HIGH.color, 0.6),
  0.62, hexA(RISK.SEVERE.color, 0.7),
  0.87, hexA(RISK.NO_TRAVEL.color, 0.8),
];

/** Exact cells at high zoom: discrete level colours (grey = no forecast). */
export function cellColorExpression(layer: HeatLayer, hour: number): ExpressionSpecification {
  return [
    'match', levelExpression(layer, hour),
    0, RISK.LOW.color,
    1, RISK.MODERATE.color,
    2, RISK.HIGH.color,
    3, RISK.SEVERE.color,
    4, RISK.NO_TRAVEL.color,
    RISK.UNKNOWN.color,
  ];
}

/** Heatmap radius that covers one grid cell at every zoom (cell px ≈ step × 512·2^z / 360). */
export function radiusExpression(stepDeg: number): ExpressionSpecification {
  const cellPx = (z: number) => (stepDeg * 512 * 2 ** z) / 360;
  // ~2.2 cells: neighbours blend into one band instead of separate blobs.
  return ['interpolate', ['exponential', 2], ['zoom'], 3, 2.2 * cellPx(3), 9, 2.2 * cellPx(9)];
}

function hexA(hex: string, a: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

/**
 * Filter for the "Show at ETA" rings: checkpoints whose ETA falls in the slider's hour, or
 * none when the toggle is off. It must be an expression filter. A legacy form like
 * ['==', 1, 0] is rejected by MapLibre, and the layer is then never added.
 */
export function etaFilter(hour: number | null): FilterSpecification {
  // etaHour is always >= 0, so -1 matches nothing.
  return ['==', ['get', 'etaHour'], hour ?? -1];
}


/** Filter for the truck icons: each route's truck at the slider's hour, or none when off. */
export function truckFilter(hour: number | null): FilterSpecification {
  return ['==', ['get', 'hour'], hour ?? -1];
}
