import { Box, Tooltip } from '@mui/material';

import { formatMiles } from './format';
import { RISK } from '../theme';
import type { Level, RouteSummary } from '../types';

const PARTS: [Level, keyof RouteSummary][] = [
  ['LOW', 'low_mi'],
  ['MODERATE', 'moderate_mi'],
  ['HIGH', 'high_mi'],
  ['SEVERE', 'severe_mi'],
  ['NO_TRAVEL', 'no_travel_mi'],
  ['UNKNOWN', 'unknown_mi'],
];

/** Stacked bar of miles per risk level: compare three routes at a glance. */
export function RiskBar({ summary, total }: { summary: RouteSummary; total: number }) {
  const label = PARTS.filter(([, k]) => (summary[k] as number) > 0)
    .map(([l, k]) => `${RISK[l].label} ${formatMiles(summary[k] as number)}`)
    .join(', ');
  return (
    <Box
      role="img"
      aria-label={`Miles by risk: ${label}`}
      sx={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', bgcolor: 'divider' }}
    >
      {PARTS.map(([level, key]) => {
        const mi = summary[key] as number;
        if (mi <= 0) return null;
        return (
          <Tooltip key={level} title={`${RISK[level].label}: ${formatMiles(mi)}`}>
            <Box sx={{ width: `${(mi / total) * 100}%`, bgcolor: RISK[level].color, minWidth: 2 }} />
          </Tooltip>
        );
      })}
    </Box>
  );
}
