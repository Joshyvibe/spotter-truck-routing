import { ThemeProvider } from '@mui/material';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { makeRoute } from '../testFixtures';
import { theme } from '../theme';
import { RouteCard } from './RouteCard';

const renderCard = (over = {}) => {
  const onSelect = vi.fn();
  render(
    <ThemeProvider theme={theme}>
      <RouteCard route={makeRoute(over)} selected={false} onSelect={onSelect} onHover={() => {}} />
    </ThemeProvider>,
  );
  return onSelect;
};

describe('RouteCard', () => {
  it('shows the Recommended chip and the risk miles', () => {
    renderCard();
    expect(screen.getByText('Recommended')).toBeInTheDocument();
    expect(screen.getByText('1h 45m')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /High 25 mi/ })).toBeInTheDocument();
  });

  it('has no chip when not recommended and selects on click', async () => {
    const onSelect = renderCard({ id: 'B', label: 'Route B', is_recommended: false });
    expect(screen.queryByText('Recommended')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Route B/ }));
    expect(onSelect).toHaveBeenCalledWith('B');
  });
});
