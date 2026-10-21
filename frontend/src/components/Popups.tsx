import { Box, Divider, Stack, Typography } from '@mui/material';
import { Popup } from 'react-map-gl/maplibre';

import { LevelChip } from './LevelChip';
import { formatDuration, formatMiles, formatNumber, formatTime } from './format';
import type { Plan, Route } from '../types';

function Row({ k, v }: { k: string; v: string }) {
  return (
    <Stack direction="row" justifyContent="space-between" spacing={2}>
      <Typography variant="caption" color="text.secondary">
        {k}
      </Typography>
      <Typography variant="caption" fontWeight={600}>
        {v}
      </Typography>
    </Stack>
  );
}

const KIND = { origin: 'Origin', destination: 'Destination', checkpoint: 'Checkpoint' } as const;

export function CheckpointPopup({
  plan,
  routeId,
  index,
  onClose,
}: {
  plan: Plan;
  routeId: string;
  index: number;
  onClose: () => void;
}) {
  const route = plan.routes.find((r) => r.id === routeId);
  const c = route?.checkpoints[index];
  if (!route || !c) return null;
  return (
    <Popup
      longitude={c.lng}
      latitude={c.lat}
      onClose={onClose}
      closeOnClick={false} // MapView's click handler decides (see MapView onClick)
      maxWidth="280px"
      offset={10}
    >
      <Box sx={{ minWidth: 220, p: 0.5 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 0.5 }}>
          <Typography variant="subtitle2">
            {route.label} · {KIND[c.kind]} · mile {c.mile.toFixed(0)}
          </Typography>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <LevelChip level={c.level} />
          <Typography variant="caption" color="text.secondary">
            ETA {formatTime(c.eta)}
          </Typography>
        </Stack>
        <Typography variant="body2" sx={{ mb: 1 }}>
          {c.reason}
        </Typography>
        <Divider sx={{ mb: 1 }} />
        <Stack spacing={0.25}>
          <Row k="Wind (sustained)" v={formatNumber(c.wind_mph, 1, 'mph')} />
          <Row k="Gusts (info only)" v={formatNumber(c.gust_mph, 1, 'mph')} />
          <Row k="Rain" v={formatNumber(c.rain_in, 2, 'in/hr')} />
          <Row k="Snow" v={formatNumber(c.snow_in, 2, 'in/hr')} />
        </Stack>
      </Box>
    </Popup>
  );
}

export function RoutePopup({ route }: { route: Route }) {
  const s = route.summary;
  return (
    <Box sx={{ minWidth: 200, p: 0.5 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        {route.label}
        {route.is_recommended ? ' · Recommended' : ` · Rank ${route.rank}`}
      </Typography>
      <Stack spacing={0.25}>
        <Row k="Distance" v={formatMiles(route.distance_mi)} />
        <Row k="Drive time" v={formatDuration(route.duration_s)} />
        <Row k="Arrive" v={formatTime(route.arrive_at)} />
        <Divider sx={{ my: 0.5 }} />
        <Row k="No Travel" v={formatMiles(s.no_travel_mi)} />
        <Row k="Severe" v={formatMiles(s.severe_mi)} />
        <Row k="High" v={formatMiles(s.high_mi)} />
        <Row k="Moderate" v={formatMiles(s.moderate_mi)} />
        <Row k="Low" v={formatMiles(s.low_mi)} />
        {s.unknown_mi > 0 && <Row k="No forecast" v={formatMiles(s.unknown_mi)} />}
        <Row k="Average risk" v={s.avg_risk === null ? '—' : s.avg_risk.toFixed(2)} />
      </Stack>
    </Box>
  );
}
