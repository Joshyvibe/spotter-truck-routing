import { Chip, type ChipProps } from '@mui/material';

import { RISK } from '../theme';
import type { Level } from '../types';

/** Colour plus text label, so colour is never the only signal. */
export function LevelChip({ level, size = 'small', ...rest }: { level: Level } & ChipProps) {
  const r = RISK[level];
  return (
    <Chip
      size={size}
      label={r.label}
      sx={{ bgcolor: r.color, color: r.text, height: 22, '& .MuiChip-label': { px: 1 } }}
      {...rest}
    />
  );
}
