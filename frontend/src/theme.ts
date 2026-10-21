import { createTheme } from '@mui/material/styles';

import type { Level } from './types';

export const SIDEBAR_WIDTH = 400;

export const theme = createTheme({
  spacing: 8,
  shape: { borderRadius: 8 },
  palette: {
    mode: 'light',
    primary: { main: '#0B3C49' }, // deep teal
    secondary: { main: '#E8505B' },
    background: { default: '#F4F6F8', paper: '#FFFFFF' },
    text: { primary: '#14212B', secondary: '#55636E' },
    divider: '#E1E6EA',
  },
  typography: {
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    h6: { fontWeight: 600, letterSpacing: '-0.01em' },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
    overline: { fontWeight: 600, letterSpacing: '0.08em' },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        // Numbers line up in every list and table.
        body: { fontVariantNumeric: 'tabular-nums' },
        'html, body, #root': { height: '100%' },
      },
    },
    MuiPaper: { defaultProps: { elevation: 0 } },
    MuiCard: { styleOverrides: { root: { border: '1px solid #E1E6EA' } } },
    MuiTextField: { defaultProps: { size: 'small', fullWidth: true } },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
  },
});

/** One palette for chips, risk bar, route segments, checkpoints, heatmap ramp and legend. */
export const RISK: Record<Level, { label: string; color: string; text: string; index: number }> = {
  LOW: { label: 'Low', color: '#2E7D32', text: '#FFFFFF', index: 0 },
  MODERATE: { label: 'Moderate', color: '#F9A825', text: '#1A1A1A', index: 1 },
  HIGH: { label: 'High', color: '#EF6C00', text: '#FFFFFF', index: 2 },
  SEVERE: { label: 'Severe', color: '#C62828', text: '#FFFFFF', index: 3 },
  NO_TRAVEL: { label: 'No Travel', color: '#4A148C', text: '#FFFFFF', index: 4 },
  UNKNOWN: { label: 'Unknown', color: '#9E9E9E', text: '#1A1A1A', index: -1 },
};

export const LEVEL_ORDER: Level[] = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL', 'UNKNOWN'];

/** MapLibre `match` expression: level string -> colour. */
export function levelColorExpression(prop = 'level'): unknown[] {
  return [
    'match',
    ['get', prop],
    ...LEVEL_ORDER.flatMap((l) => [l, RISK[l].color]),
    RISK.UNKNOWN.color,
  ];
}
