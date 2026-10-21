import PlaceOutlined from '@mui/icons-material/PlaceOutlined';
import { Autocomplete, InputAdornment, TextField } from '@mui/material';
import { useEffect, useState } from 'react';

import { useGeocode } from '../hooks/queries';
import type { Place } from '../types';

interface Props {
  label: string;
  value: string | Place | null;
  onChange: (v: string | Place | null) => void;
  error?: string;
  autoFocus?: boolean;
}

/** Free text or a suggestion. Suggestions come from the server proxy (key stays server-side). */
export function PlaceAutocomplete({ label, value, onChange, error, autoFocus }: Props) {
  const [input, setInput] = useState(typeof value === 'string' ? value : (value?.label ?? ''));
  const [debounced, setDebounced] = useState(input);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(input), 300); // DESIGN §6: 300 ms debounce
    return () => clearTimeout(t);
  }, [input]);

  useEffect(() => {
    setInput(typeof value === 'string' ? value : (value?.label ?? ''));
  }, [value]);

  const { data: options = [], isFetching } = useGeocode(debounced);

  return (
    <Autocomplete<Place, false, false, true>
      freeSolo
      options={options}
      filterOptions={(x) => x}
      getOptionLabel={(o) => (typeof o === 'string' ? o : o.label)}
      isOptionEqualToValue={(a, b) => a.label === b.label}
      value={value}
      inputValue={input}
      loading={isFetching}
      onInputChange={(_, v, reason) => {
        setInput(v);
        if (reason === 'input') onChange(v);
      }}
      onChange={(_, v) => onChange(v)}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          autoFocus={autoFocus}
          error={Boolean(error)}
          helperText={error}
          InputProps={{
            ...params.InputProps,
            startAdornment: (
              <InputAdornment position="start">
                <PlaceOutlined fontSize="small" color="action" />
              </InputAdornment>
            ),
          }}
        />
      )}
    />
  );
}
