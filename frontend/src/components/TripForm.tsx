import LocalShippingOutlined from '@mui/icons-material/LocalShippingOutlined';
import {
  Box,
  Button,
  CircularProgress,
  InputAdornment,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import dayjs from 'dayjs';
import { useEffect, useState, type FormEvent } from 'react';

import { ApiError } from '../api/client';
import {
  MAX_LOAD_LB,
  defaultDeparture,
  validateTrip,
  type TripErrors,
  type TripValues,
} from './validateTrip';
import type { PlanRequest } from '../types';
import { PlaceAutocomplete } from './PlaceAutocomplete';

const INTERVAL_HELP: Record<10 | 25 | 50, string> = {
  10: 'Most detail: catches small storm cells (~7.5 mi wide). More lookups.',
  25: 'Balanced detail and speed (default).',
  50: 'Fastest, but can step over a storm between checkpoints.',
};

interface Props {
  initial?: TripValues;
  submitting: boolean;
  serverError: unknown;
  onSubmit: (req: PlanRequest) => void;
}

export function TripForm({ initial, submitting, serverError, onSubmit }: Props) {
  const [v, setV] = useState<TripValues>(
    initial ?? {
      origin: null,
      destination: null,
      departAt: defaultDeparture(),
      loadLb: '',
      intervalMi: 25,
    },
  );
  const [errors, setErrors] = useState<TripErrors>({});

  useEffect(() => {
    if (initial) setV(initial);
  }, [initial]);

  // Server-side field errors (e.g. a place that does not geocode) land on the matching input.
  useEffect(() => {
    if (serverError instanceof ApiError && serverError.field) {
      setErrors((e) => ({ ...e, [serverError.field as keyof TripErrors]: serverError.message }));
    }
  }, [serverError]);

  const set = <K extends keyof TripValues>(k: K, val: TripValues[K]) => {
    setV((s) => ({ ...s, [k]: val }));
    const field = k === 'departAt' ? 'depart_at' : k === 'loadLb' ? 'load_lb' : k;
    setErrors((e) => ({ ...e, [field]: undefined }));
  };

  const submit = (ev: FormEvent) => {
    ev.preventDefault();
    const found = validateTrip(v);
    setErrors(found);
    if (Object.values(found).some(Boolean)) return;
    onSubmit({
      origin: v.origin!,
      destination: v.destination!,
      depart_at: v.departAt!.format(), // ISO 8601 with the browser's offset
      load_lb: Number(v.loadLb),
      interval_mi: v.intervalMi,
    });
  };

  return (
    <Box component="form" noValidate onSubmit={submit} aria-label="Plan a trip">
      <Stack spacing={2}>
        <PlaceAutocomplete
          label="Origin"
          value={v.origin}
          onChange={(x) => set('origin', x)}
          error={errors.origin}
        />
        <PlaceAutocomplete
          label="Destination"
          value={v.destination}
          onChange={(x) => set('destination', x)}
          error={errors.destination}
        />
        <DateTimePicker
          label="Departure"
          value={v.departAt}
          onChange={(x) => set('departAt', x)}
          disablePast={false}
          minDateTime={dayjs().subtract(1, 'hour')}
          maxDateTime={dayjs().add(7, 'day')}
          ampm={false}
          slotProps={{
            textField: {
              size: 'small',
              fullWidth: true,
              error: Boolean(errors.depart_at),
              helperText: errors.depart_at ?? `Your local time (${dayjs().format('Z')})`,
            },
          }}
        />
        <TextField
          label="Load weight"
          value={v.loadLb}
          onChange={(e) => set('loadLb', e.target.value.replace(/[^\d]/g, ''))}
          inputMode="numeric"
          error={Boolean(errors.load_lb)}
          helperText={errors.load_lb ?? `Cargo only, up to ${MAX_LOAD_LB.toLocaleString()} lb`}
          InputProps={{ endAdornment: <InputAdornment position="end">lb</InputAdornment> }}
          inputProps={{ 'aria-label': 'Load weight in pounds' }}
        />
        <Box>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 0.5 }}>
            Weather checkpoint every
          </Typography>
          <ToggleButtonGroup
            exclusive
            fullWidth
            size="small"
            color="primary"
            value={v.intervalMi}
            onChange={(_, x) => x && set('intervalMi', x)}
            aria-label="Checkpoint interval"
          >
            {([10, 25, 50] as const).map((n) => (
              <ToggleButton key={n} value={n} aria-label={`${n} miles`}>
                {n} mi
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            {INTERVAL_HELP[v.intervalMi]}
          </Typography>
        </Box>
        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={submitting}
          startIcon={
            submitting ? <CircularProgress size={18} color="inherit" /> : <LocalShippingOutlined />
          }
        >
          {submitting ? 'Planning routes…' : 'Plan route'}
        </Button>
      </Stack>
    </Box>
  );
}
