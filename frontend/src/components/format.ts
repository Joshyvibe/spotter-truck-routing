const timeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZoneName: 'short',
});
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZoneName: 'short',
});

/** "Wed 14:00 CDT" — always with the zone, so nobody guesses which clock it is. */
export const formatTime = (iso: string) => timeFmt.format(new Date(iso)).replace(',', '');
export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso));

export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}m`;
}

export const formatMiles = (mi: number) =>
  `${mi.toLocaleString(undefined, { maximumFractionDigits: mi < 10 ? 1 : 0 })} mi`;

export const formatNumber = (v: number | null, digits: number, unit: string) =>
  v === null ? '—' : `${v.toFixed(digits)} ${unit}`;

const shortFmt = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});
/** "Tue 16:45" — for dense tables where the zone is shown once in the header. */
export const formatTimeShort = (iso: string) => shortFmt.format(new Date(iso)).replace(',', '');

/** The browser's short zone name at a given moment, e.g. "CDT" or "GMT+1". */
export function zoneName(iso: string): string {
  const part = timeFmt.formatToParts(new Date(iso)).find((p) => p.type === 'timeZoneName');
  return part?.value ?? '';
}
