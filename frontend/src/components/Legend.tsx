import { Box, Paper, Stack, Typography } from '@mui/material';

import { LEVEL_ORDER, RISK } from '../theme';

/** Vertical on desktop; a compact single row on phones so it doesn't cover the small map. */
export function Legend({ compact = false }: { compact?: boolean }) {
  return (
    <Paper sx={{ px: 1.5, py: compact ? 0.5 : 1, border: 1, borderColor: 'divider' }} aria-label="Risk legend">
      {!compact && (
        <Typography variant="overline" color="text.secondary" sx={{ lineHeight: 1.5 }}>
          Risk
        </Typography>
      )}
      <Stack direction={compact ? 'row' : 'column'} spacing={compact ? 1 : 0.5} flexWrap="wrap" useFlexGap>
        {LEVEL_ORDER.map((l) => (
          <Stack key={l} direction="row" spacing={0.5} alignItems="center">
            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: RISK[l].color }} />
            <Typography variant="caption" sx={{ lineHeight: 1.4 }}>
              {RISK[l].label}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Paper>
  );
}
