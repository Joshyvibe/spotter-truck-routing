import { makePlan } from '../testFixtures';
import {
  SLIDER_HOURS,
  bounds,
  checkpointPoints,
  decode,
  riskSegments,
  routeLabels,
  routeLines,
  truckPositions,
} from './geojson';

describe('geojson builders', () => {
  const plan = makePlan();

  it('decodes polylines to [lng, lat]', () => {
    expect(decode(plan.routes[0]!.geometry)[0]).toEqual([-100, 40]);
  });

  it('builds one line per route with its id', () => {
    const fc = routeLines(plan);
    expect(fc.features.map((f) => f.properties?.routeId)).toEqual(['A', 'B']);
  });

  it('keeps risk levels on segments', () => {
    expect(riskSegments(plan).features.map((f) => f.properties?.level)).toEqual(['LOW', 'HIGH', 'LOW', 'HIGH']);
  });

  it('computes ETA hour after departure for each checkpoint', () => {
    const hours = checkpointPoints(plan).features.map((f) => f.properties?.etaHour);
    expect(hours.slice(0, 2)).toEqual([0, 2]);
  });

  it('labels routes and fits bounds around all of them', () => {
    expect(routeLabels(plan, (id) => `x${id}`).features[1]!.properties?.text).toBe('xB');
    expect(bounds(plan)).toEqual([[-100, 39], [-98, 41]]);
  });
});

describe('truckPositions', () => {
  // Route A in the fixture: mile 0 at 13:00 (departure), mile 100 at 15:00, along
  // (40,-100) -> (40.5,-99) -> (41,-98).
  const plan = makePlan();
  const trucks = truckPositions(plan).features;
  const at = (routeId: string, hour: number) =>
    trucks.find((f) => f.properties?.routeId === routeId && f.properties?.hour === hour)!;

  it('has one truck per route for every slider hour', () => {
    expect(trucks).toHaveLength(plan.routes.length * SLIDER_HOURS);
  });

  it('starts at the origin at departure and moves along the road by ETA', () => {
    expect(at('A', 0).geometry.coordinates).toEqual([-100, 40]);
    const [lng, lat] = at('A', 1).geometry.coordinates as [number, number];
    // 1 h of a 2 h drive = mile 50 of 100: the line's midpoint
    expect(lng).toBeCloseTo(-99, 1);
    expect(lat).toBeCloseTo(40.5, 1);
    expect(at('A', 1).properties?.arrived).toBe(false);
  });

  it('waits at the destination after arrival', () => {
    expect(at('A', 2).geometry.coordinates).toEqual([-98, 41]);
    expect(at('A', 30).geometry.coordinates).toEqual([-98, 41]);
    expect(at('A', 30).properties?.arrived).toBe(true);
  });
});
