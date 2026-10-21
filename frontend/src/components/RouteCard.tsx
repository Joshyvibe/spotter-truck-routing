import StarRounded from '@mui/icons-material/StarRounded';
import { Box, Card, CardActionArea, Chip, Stack, Typography } from '@mui/material';
import { memo } from 'react';

import { formatDuration, formatMiles, formatTime } from './format';
import { RISK } from '../theme';
import type { Route } from '../types';
import { RiskBar } from './RiskBar';

interface Props {
  route: Route;
  selected: boolean;
  hovered?: boolean; // hovering this route's line on the map

  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary" noWrap component="div">
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={600} noWrap sx={{ color }}>
        {value}
      </Typography>
    </Box>
  );
}

export const RouteCard = memo(function RouteCard({ route, selected, hovered = false, onSelect, onHover }: Props) {
  const s = route.summary;
  return (
    <Card
      sx={{
        borderColor: selected ? 'primary.main' : hovered ? 'text.secondary' : 'divider',
        bgcolor: hovered && !selected ? 'action.hover' : 'background.paper',
        boxShadow: selected ? (t) => `0 0 0 1px ${t.palette.primary.main}` : 'none',
        transition: 'border-color 120ms, box-shadow 120ms, background-color 120ms',
      }}
      onMouseEnter={() => onHover(route.id)}
      onMouseLeave={() => onHover(null)}
    >
      <CardActionArea onClick={() => onSelect(route.id)} aria-pressed={selected} sx={{ p: 2 }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
          <Typography variant="subtitle1">{route.label}</Typography>
          {route.is_recommended && (
            <Chip
              size="small"
              color="primary"
              icon={<StarRounded />}
              label="Recommended"
              sx={{ height: 22 }}
            />
          )}
        </Stack>
        <Box sx={{ display: 'grid', gridTemplateColumns: '0.9fr 0.9fr 1.4fr', gap: 1, mb: 1.5 }}>
          <Stat label="Distance" value={formatMiles(route.distance_mi)} />
          <Stat label="Drive time" value={formatDuration(route.duration_s)} />
          <Stat label="Arrive" value={formatTime(route.arrive_at)} />
        </Box>
        <RiskBar summary={s} total={route.distance_mi} />
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, mt: 1.5 }}>
          <Stat
            label="No Travel"
            value={formatMiles(s.no_travel_mi)}
            color={s.no_travel_mi > 0 ? RISK.NO_TRAVEL.color : undefined}
          />
          <Stat
            label="Severe"
            value={formatMiles(s.severe_mi)}
            color={s.severe_mi > 0 ? RISK.SEVERE.color : undefined}
          />
          <Stat
            label="High"
            value={formatMiles(s.high_mi)}
            color={s.high_mi > 0 ? RISK.HIGH.color : undefined}
          />
          <Stat label="Avg risk" value={s.avg_risk === null ? '—' : s.avg_risk.toFixed(2)} />
        </Box>
      </CardActionArea>
    </Card>
  );
});
