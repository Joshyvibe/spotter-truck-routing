import { createContext } from 'react';

export interface SelectionState {
  selectedRouteId: string | null;
  hoveredRouteId: string | null;
  selectedCheckpoint: { routeId: string; index: number } | null;
}

export type Action =
  | { type: 'select'; routeId: string }
  | { type: 'hover'; routeId: string | null }
  | { type: 'checkpoint'; routeId: string; index: number }
  | { type: 'clearCheckpoint' }
  | { type: 'reset'; routeId: string | null };

export const SelectionContext = createContext<{
  state: SelectionState;
  dispatch: (a: Action) => void;
} | null>(null);
