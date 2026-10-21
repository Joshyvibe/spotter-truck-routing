import dayjs, { type Dayjs } from 'dayjs';

import type { Place, Plan } from '../types';

export interface TripValues {
  origin: string | Place | null;
  destination: string | Place | null;
  departAt: Dayjs | null;
  loadLb: string;
  intervalMi: 10 | 25 | 50;
}

export type TripErrors = Partial<Record<'origin' | 'destination' | 'depart_at' | 'load_lb', string>>;

export const MAX_LOAD_LB = 80_000;
const HOUR = 3_600_000;

const placeText = (p: string | Place | null) => (typeof p === 'string' ? p.trim() : p?.label ?? '');

/** Mirrors the server rules so most mistakes are caught before a round trip. */
export function validateTrip(v: TripValues, now = Date.now()): TripErrors {
  const e: TripErrors = {};
  if (!placeText(v.origin)) e.origin = 'Enter an origin.';
  if (!placeText(v.destination)) e.destination = 'Enter a destination.';
  else if (placeText(v.origin).toLowerCase() === placeText(v.destination).toLowerCase())
    e.destination = 'Origin and destination must be different places.';
  if (!v.departAt || !v.departAt.isValid()) e.depart_at = 'Pick a departure date and time.';
  else if (v.departAt.valueOf() < now - HOUR) e.depart_at = 'Departure can be at most 1 hour in the past.';
  else if (v.departAt.valueOf() > now + 7 * 24 * HOUR)
    e.depart_at = 'Departure must be within the next 7 days (forecast range).';
  const load = Number(v.loadLb);
  if (!v.loadLb.trim()) e.load_lb = 'Enter the load weight.';
  else if (!Number.isInteger(load) || load <= 0) e.load_lb = 'Enter a whole number of pounds above 0.';
  else if (load > MAX_LOAD_LB) e.load_lb = `Maximum is ${MAX_LOAD_LB.toLocaleString()} lb.`;
  return e;
}

export function defaultDeparture() {
  // Next quarter hour, one hour from now.
  const t = dayjs().add(1, 'hour');
  return t.minute(Math.ceil(t.minute() / 15) * 15).second(0).millisecond(0);
}

export function valuesFromPlan(plan: Plan): TripValues {
  return {
    origin: plan.origin,
    destination: plan.destination,
    departAt: dayjs(plan.depart_at),
    loadLb: String(plan.load_lb),
    intervalMi: plan.interval_mi,
  };
}
