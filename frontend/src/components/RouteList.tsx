import { Stack } from '@mui/material';

import type { Route } from '../types';
import { RouteCard } from './RouteCard';

interface Props {
  routes: Route[];
  selectedId: string | undefined;
  hoveredId: string | null;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

/** The 3 route options, best first (the API returns them sorted by rank). */
export function RouteList({ routes, selectedId, hoveredId, onSelect, onHover }: Props) {
  return (
    <Stack spacing={1.5}>
      {routes.map((r) => (
        <RouteCard
          key={r.id}
          route={r}
          selected={r.id === selectedId}
          hovered={r.id === hoveredId}
          onSelect={onSelect}
          onHover={onHover}
        />
      ))}
    </Stack>
  );
}
