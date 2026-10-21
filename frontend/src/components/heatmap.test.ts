/**
 * Evaluates the real MapLibre expressions with MapLibre's own engine, so the colours on the
 * map provably follow the brief's thresholds (the same boundaries as backend test_risk.py).
 */
import { createExpression } from '@maplibre/maplibre-gl-style-spec';

import type { HeatLayer, Heatmap } from '../types';
import { cellColorExpression, heatmapSource, levelExpression, weightExpression } from './heatmap';
import { RISK } from '../theme';

function evaluate(expr: unknown, properties: Record<string, number>) {
  const parsed = createExpression(expr, { type: 'number' } as never);
  if (parsed.result !== 'success') throw new Error(JSON.stringify(parsed.value));
  const feature = { type: 'Point', properties, geometry: [] } as never;
  return parsed.value.evaluate({ zoom: 5 } as never, feature);
}

const level = (layer: HeatLayer, value?: number) =>
  evaluate(levelExpression(layer, 3), value === undefined ? {} : { [`${layer[0]}3`]: value });

describe('levelExpression follows the brief table', () => {
  it.each([
    [0, 0], [24.99, 0], [25, 1], [34.99, 1], [35, 2], [44.99, 2], [45, 3], [54.99, 3], [55, 4],
  ])('wind %s mph -> level %s', (mph, expected) => {
    expect(level('wind', mph)).toBe(expected);
  });

  it.each([
    [0.0999, 0], [0.1, 1], [0.25, 2], [0.5, 3], [1.0, 3], [1.0001, 4],
  ])('rain %s in/hr -> level %s', (rain, expected) => {
    expect(level('precip', rain)).toBe(expected);
  });

  it.each([
    [0.499, 0], [0.5, 1], [1.0, 2], [2.0, 3], [3.0, 3], [3.01, 4],
  ])('snow %s in/hr -> level %s', (snow, expected) => {
    expect(level('snow', snow)).toBe(expected);
  });

  it('passes the server risk level through and marks missing data as -1', () => {
    expect(level('risk', 3)).toBe(3);
    expect(level('wind')).toBe(-1);
  });
});

describe('weight and colour', () => {
  it('weights by level / 4 and gives unknown no weight', () => {
    expect(evaluate(weightExpression('risk', 3), { r3: 4 })).toBe(1);
    expect(evaluate(weightExpression('risk', 3), { r3: 2 })).toBe(0.5);
    expect(evaluate(weightExpression('risk', 3), {})).toBe(0);
  });

  it('colours cells with the shared palette', () => {
    const color = (props: Record<string, number>) => {
      const parsed = createExpression(cellColorExpression('risk', 3), { type: 'color' } as never);
      if (parsed.result !== 'success') throw new Error('bad expression');
      return parsed.value.evaluate({ zoom: 8 } as never, { type: 'Point', properties: props, geometry: [] } as never).toString();
    };
    const css = (hex: string) => {
      const n = parseInt(hex.slice(1), 16);
      return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},1)`;
    };
    expect(color({ r3: 4 })).toBe(css(RISK.NO_TRAVEL.color));
    expect(color({ r3: 0 })).toBe(css(RISK.LOW.color));
    expect(color({})).toBe(css(RISK.UNKNOWN.color));
  });
});

describe('heatmapSource', () => {
  it('turns the column-shaped grid into one feature per point with per-hour properties', () => {
    const h: Heatmap = {
      plan_id: 'p', start: '2026-10-21T13:00:00Z', hours: 2, forecast_as_of: '', grid_step_deg: 0.25,
      bbox: [0, 0, 0, 0], points: [[40, -100], [41, -101]],
      risk: [[0, 4], [null, 2]], wind: [[10, 60], [11, 40]], precip: [[0, 0], [0, 0]], snow: [[0, 0], [0, 0]],
    };
    const fc = heatmapSource(h);
    expect(fc.features).toHaveLength(2);
    expect(fc.features[1]!.geometry.coordinates).toEqual([-101, 41]);
    expect(fc.features[1]!.properties).toMatchObject({ r0: 4, r1: 2, w0: 60, w1: 40 });
    expect(fc.features[0]!.properties).not.toHaveProperty('r1'); // null stays absent
  });
});

describe('etaFilter', () => {
  // MapLibre's own filter compiler: it throws on anything it would refuse to add to the map.
  const compile = async (f: unknown) =>
    (await import('@maplibre/maplibre-gl-style-spec')).featureFilter(f as never);
  const at = (etaHour: number) => ({ type: 1, properties: { etaHour }, geometry: [] }) as never;

  it('is a filter MapLibre accepts, both on and off', async () => {
    const { etaFilter } = await import('./heatmap');
    await expect(compile(etaFilter(6))).resolves.toBeDefined();
    await expect(compile(etaFilter(null))).resolves.toBeDefined();
    // The legacy form that broke the layer is rejected, so this test would catch it.
    await expect(compile(['==', 1, 0])).rejects.toThrow();
  });

  it('selects only checkpoints in the slider hour, and none when off', async () => {
    const { etaFilter } = await import('./heatmap');
    const on = await compile(etaFilter(6));
    const off = await compile(etaFilter(null));
    expect(on.filter({ zoom: 5 } as never, at(6))).toBe(true);
    expect(on.filter({ zoom: 5 } as never, at(5))).toBe(false);
    expect([0, 6, 48].some((h) => off.filter({ zoom: 5 } as never, at(h)))).toBe(false);
  });
});

describe('truckFilter', () => {
  it('is a filter MapLibre accepts and picks one hour, or nothing when off', async () => {
    const { featureFilter } = await import('@maplibre/maplibre-gl-style-spec');
    const { truckFilter } = await import('./heatmap');
    const at = (hour: number) => ({ type: 1, properties: { hour }, geometry: [] }) as never;
    const on = featureFilter(truckFilter(6) as never);
    const off = featureFilter(truckFilter(null) as never);
    expect(on.filter({ zoom: 5 } as never, at(6))).toBe(true);
    expect(on.filter({ zoom: 5 } as never, at(7))).toBe(false);
    expect(off.filter({ zoom: 5 } as never, at(0))).toBe(false);
  });
});
