import { Alert, AlertTitle, Stack, Typography } from '@mui/material';

import { formatDateTime } from './format';
import type { Plan } from '../types';

export function RecommendationAlert({ plan }: { plan: Plan }) {
  return (
    <Stack spacing={1}>
      {plan.all_routes_unsafe && (
        <Alert severity="error" variant="filled">
          <AlertTitle>No safe route at this departure time</AlertTitle>
          Every route crosses No Travel conditions. Try departing later; use the forecast slider
          to find a calmer window.
        </Alert>
      )}
      <Alert severity={plan.all_routes_unsafe ? 'warning' : 'success'} icon={false}>
        <Typography variant="body2" fontWeight={600}>
          {plan.recommendation_reason}
        </Typography>
      </Alert>
      {plan.warnings.map((w) => (
        <Alert key={w} severity="warning" sx={{ py: 0 }}>
          {w}
        </Alert>
      ))}
      <Typography variant="caption" color="text.secondary">
        Forecast as of {formatDateTime(plan.forecast_as_of)} · ETAs are drive time without
        hours-of-service breaks
      </Typography>
    </Stack>
  );
}
