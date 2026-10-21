import { useMemo, useReducer, type ReactNode } from 'react';

import { SelectionContext as Ctx, type Action, type SelectionState } from './selectionContext';

function reducer(state: SelectionState, a: Action): SelectionState {
  switch (a.type) {
    case 'select':
      return state.selectedRouteId === a.routeId ? state : { ...state, selectedRouteId: a.routeId };
    case 'hover':
      return state.hoveredRouteId === a.routeId ? state : { ...state, hoveredRouteId: a.routeId };
    case 'checkpoint':
      return { ...state, selectedRouteId: a.routeId, selectedCheckpoint: { routeId: a.routeId, index: a.index } };
    case 'clearCheckpoint':
      return { ...state, selectedCheckpoint: null };
    case 'reset':
      return { selectedRouteId: a.routeId, hoveredRouteId: null, selectedCheckpoint: null };
  }
}


export function SelectionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    selectedRouteId: null,
    hoveredRouteId: null,
    selectedCheckpoint: null,
  });
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
