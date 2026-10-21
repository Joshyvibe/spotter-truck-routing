import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { memo } from 'react';

import { formatTimeShort, zoneName } from './format';
import type { Route } from '../types';
import { LevelChip } from './LevelChip';

const num = (v: number | null, digits: number) => (v === null ? '—' : v.toFixed(digits));

function Unit({ children }: { children: string }) {
  return (
    <Typography variant="caption" color="text.secondary" component="div" sx={{ fontWeight: 400 }}>
      {children}
    </Typography>
  );
}

interface Props {
  route: Route;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}

export const CheckpointTable = memo(function CheckpointTable({ route, selectedIndex, onSelect }: Props) {
  return (
    <TableContainer sx={{ border: 1, borderColor: 'divider', borderRadius: 1 }}>
      <Table
        size="small"
        stickyHeader
        aria-label={`${route.label} checkpoints`}
        sx={{ '& td, & th': { px: 1 }, '& td:first-of-type, & th:first-of-type': { pl: 1.5 } }}
      >
        <TableHead>
          <TableRow sx={{ '& th': { lineHeight: 1.2, verticalAlign: 'bottom' } }}>
            <TableCell align="right">Mile</TableCell>
            <TableCell>
              ETA
              <Unit>{zoneName(route.checkpoints[0]?.eta ?? new Date().toISOString())}</Unit>
            </TableCell>
            <TableCell>Risk</TableCell>
            <TableCell align="right">
              Wind<Unit>mph</Unit>
            </TableCell>
            <TableCell align="right">
              Rain<Unit>in/hr</Unit>
            </TableCell>
            <TableCell align="right">
              Snow<Unit>in/hr</Unit>
            </TableCell>
            <TableCell>Reason</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {route.checkpoints.map((c) => (
            <TableRow
              key={c.index}
              hover
              selected={c.index === selectedIndex}
              onClick={() => onSelect(c.index)}
              sx={{ cursor: 'pointer', '& td': { whiteSpace: 'nowrap' } }}
            >
              <TableCell align="right">{c.mile.toFixed(0)}</TableCell>
              <TableCell>{formatTimeShort(c.eta)}</TableCell>
              <TableCell>
                <LevelChip level={c.level} />
              </TableCell>
              <TableCell align="right">{num(c.wind_mph, 1)}</TableCell>
              <TableCell align="right">{num(c.rain_in, 2)}</TableCell>
              <TableCell align="right">{num(c.snow_in, 2)}</TableCell>
              {/* The reason wraps; the table scrolls sideways inside the 400 px sidebar. */}
              <TableCell sx={{ whiteSpace: 'normal !important', minWidth: 180 }}>
                <Typography variant="caption">{c.reason}</Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
});
