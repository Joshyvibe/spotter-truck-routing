/**
 * The 0–48 h forecast slider. Its state lives here, inside the map, so scrubbing never
 * re-renders the sidebar or rebuilds map data. Each change only swaps paint expressions and a
 * filter (one batch per animation frame): no setData, no network.
 */
import PauseRounded from '@mui/icons-material/PauseRounded';
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded';
import {
  Alert,
  Box,
  Button,
  FormControlLabel,
  IconButton,
  LinearProgress,
  Paper,
  Slider,
  Stack,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useEffect, useRef, useState } from 'react';
import { useMap } from 'react-map-gl/maplibre';

import { formatDateTime } from './format';
import { HEAT_LAYERS, type HeatLayer } from '../types';
import {
  LAYER_INFO,
  cellColorExpression,
  etaFilter,
  truckFilter,
  weightExpression,
} from './heatmap';

const PLAY_STEP_MS = 450;

interface Props {
  start: string | undefined; // heatmap hour 0 = departure
  hours: number;
  ready: boolean;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function HeatmapControls({ start, hours, ready, loading, error, onRetry }: Props) {
  const { current: mapRef } = useMap();
  const [hour, setHour] = useState(0);
  const [layer, setLayer] = useState<HeatLayer>('risk');
  const [visible, setVisible] = useState(true);
  const [atEta, setAtEta] = useState(true); // on by default (TECHNICAL_DESIGN §9, D5)
  const [playing, setPlaying] = useState(false);
  const frame = useRef<number | null>(null);
  const maxHour = Math.max(0, hours - 1);

  // Apply the current state to the map, at most once per animation frame.
  useEffect(() => {
    const map = mapRef?.getMap();
    if (!map) return;
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      if (map.getLayer('heat')) {
        map.setPaintProperty('heat', 'heatmap-weight', weightExpression(layer, hour));
        map.setLayoutProperty('heat', 'visibility', visible ? 'visible' : 'none');
      }
      if (map.getLayer('heat-cells')) {
        map.setPaintProperty('heat-cells', 'circle-color', cellColorExpression(layer, hour));
        map.setLayoutProperty('heat-cells', 'visibility', visible ? 'visible' : 'none');
      }
      // "Where is the truck at hour X?" next to "what is the weather at hour X?"
      if (map.getLayer('checkpoints-eta')) {
        map.setFilter('checkpoints-eta', etaFilter(atEta ? hour : null));
      }
      if (map.getLayer('trucks')) map.setFilter('trucks', truckFilter(atEta ? hour : null));
    });
  }, [mapRef, hour, layer, visible, atEta, ready]);

  useEffect(() => () => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
  }, []);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setHour((h) => {
        if (h >= maxHour) {
          setPlaying(false);
          return h;
        }
        return h + 1;
      });
    }, PLAY_STEP_MS);
    return () => clearInterval(id);
  }, [playing, maxHour]);

  const label = start ? formatDateTime(new Date(Date.parse(start) + hour * 3_600_000).toISOString()) : '';

  return (
    <Paper
      sx={{
        position: 'absolute',
        left: '50%',
        transform: 'translateX(-50%)',
        bottom: { xs: 28, md: 32 },
        width: 'min(560px, calc(100% - 24px))',
        px: { xs: 1.5, md: 2 },
        py: { xs: 0.75, md: 1.25 },
        border: 1,
        borderColor: 'divider',
        boxShadow: '0 4px 16px rgba(20,33,43,0.12)',
      }}
      aria-label="Weather forecast slider"
    >
      {loading && <LinearProgress sx={{ position: 'absolute', top: 0, left: 0, right: 0 }} />}
      {error ? (
        <Alert
          severity="warning"
          sx={{ py: 0 }}
          action={<Button color="inherit" size="small" onClick={onRetry}>Retry</Button>}
        >
          Weather heatmap unavailable: {error}
        </Alert>
      ) : (
        <>
          <Stack direction="row" alignItems="center" spacing={1.5}>
            <IconButton
              size="small"
              onClick={() => {
                if (hour >= maxHour) setHour(0);
                setPlaying((p) => !p);
              }}
              disabled={!ready}
              aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
            >
              {playing ? <PauseRounded /> : <PlayArrowRounded />}
            </IconButton>
            <Slider
              size="small"
              min={0}
              max={maxHour}
              step={1}
              value={hour}
              disabled={!ready}
              onChange={(_, v) => {
                setPlaying(false);
                setHour(v as number);
              }}
              marks={[0, 12, 24, 36, 48].filter((m) => m <= maxHour).map((m) => ({ value: m, label: `${m}h` }))}
              valueLabelDisplay="auto"
              valueLabelFormat={(v) => `+${v} h`}
              aria-label="Hours after departure"
              aria-valuetext={`${label}, ${hour} hours after departure`}
              sx={{ mx: 1, mb: 1, '& .MuiSlider-markLabel': { fontSize: 11, top: 22 } }}
            />
          </Stack>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            alignItems={{ xs: 'stretch', sm: 'center' }}
            justifyContent="space-between"
            spacing={1}
            sx={{ mt: 1 }}
          >
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="subtitle2" noWrap>
                {ready ? label : 'Loading forecast…'}
                <Typography component="span" variant="caption" color="text.secondary">
                  {'  '}· +{hour} h after departure
                </Typography>
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                noWrap
                component="div"
                sx={{ display: { xs: 'none', sm: 'block' } }}
              >
                {LAYER_INFO[layer].note}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ flexShrink: 0 }}>
              <ToggleButtonGroup
                size="small"
                exclusive
                value={layer}
                onChange={(_, v) => v && setLayer(v)}
                aria-label="Heatmap layer"
                sx={{ '& .MuiToggleButton-root': { py: 0.25, px: 1, fontSize: 12 } }}
              >
                {HEAT_LAYERS.map((l) => (
                  <ToggleButton key={l} value={l}>
                    {LAYER_INFO[l].label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Stack>
          </Stack>
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 0.25 }}>
            <FormControlLabel
              control={<Switch size="small" checked={visible} onChange={(e) => setVisible(e.target.checked)} />}
              label={<Typography variant="caption">Heatmap</Typography>}
            />
            <FormControlLabel
              control={<Switch size="small" checked={atEta} onChange={(e) => setAtEta(e.target.checked)} />}
              label={<Typography variant="caption">Show at ETA</Typography>}
            />
          </Stack>
        </>
      )}
    </Paper>
  );
}
