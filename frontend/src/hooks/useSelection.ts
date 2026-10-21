import { useContext } from 'react';

import { SelectionContext } from './selectionContext';

export function useSelection() {
  const v = useContext(SelectionContext);
  if (!v) throw new Error('useSelection must be used inside SelectionProvider');
  return v;
}
