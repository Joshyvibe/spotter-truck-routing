import dayjs from 'dayjs';

import { validateTrip, type TripValues } from './validateTrip';

const NOW = Date.parse('2026-10-20T12:00:00Z');
const ok: TripValues = {
  origin: 'Chicago, IL',
  destination: { lat: 39.7, lng: -105, label: 'Denver, CO' },
  departAt: dayjs(NOW + 3_600_000),
  loadLb: '42000',
  intervalMi: 25,
};

describe('validateTrip', () => {
  it('accepts a valid trip', () => {
    expect(validateTrip(ok, NOW)).toEqual({});
  });

  it.each([
    [{ origin: '  ' }, 'origin'],
    [{ destination: null }, 'destination'],
    [{ destination: 'chicago, il' }, 'destination'],
    [{ loadLb: '' }, 'load_lb'],
    [{ loadLb: '0' }, 'load_lb'],
    [{ loadLb: '80001' }, 'load_lb'],
    [{ departAt: dayjs(NOW - 2 * 3_600_000) }, 'depart_at'],
    [{ departAt: dayjs(NOW + 8 * 24 * 3_600_000) }, 'depart_at'],
  ] as const)('flags %o on %s', (over, field) => {
    expect(validateTrip({ ...ok, ...over } as TripValues, NOW)).toHaveProperty(field);
  });

  it('allows the 80,000 lb maximum and 1 hour in the past', () => {
    expect(validateTrip({ ...ok, loadLb: '80000', departAt: dayjs(NOW - 30 * 60_000) }, NOW)).toEqual({});
  });
});
