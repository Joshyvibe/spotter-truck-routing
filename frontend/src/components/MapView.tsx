/**
 * WebGL map (MapLibre). Performance rules from docs/DESIGN.md §7:
 * - no React markers: checkpoints are one circle layer on one GeoJSON source;
 * - GeoJSON is built once per plan (useMemo on plan id); hover/selection only change paint
 *   expressions, never source data;
 * - one click handler for every interactive layer.
 */
import 'maplibre-gl/dist/maplibre-gl.css';

import { Box } from '@mui/material';
import type { ExpressionSpecification, MapLayerMouseEvent } from 'maplibre-gl';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Map, {
  AttributionControl,
  Layer,
  NavigationControl,
  Popup,
  Source,
  type MapRef,
} from 'react-map-gl/maplibre';

import { useHeatmap } from '../hooks/queries';
import { Legend } from './Legend';
import { errorMessage } from '../api/errors';
import { formatDuration } from './format';
import { levelColorExpression } from '../theme';
import { useSelection } from '../hooks/useSelection';
import type { Plan } from '../types';
import { bounds, checkpointPoints, riskSegments, routeLabels, routeLines, truckPositions } from './geojson';
import {
  HEAT_COLOR,
  cellColorExpression,
  etaFilter,
  truckFilter,
  heatmapSource,
  radiusExpression,
  weightExpression,
} from './heatmap';
import { HeatmapControls } from './HeatmapControls';
import { TRUCK_ICON, addTruckIcon } from './truckIcon';
import { CheckpointPopup, RoutePopup } from './Popups';

const STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/positron';
const US_VIEW = { longitude: -96, latitude: 39, zoom: 3.6 };
const INTERACTIVE = ['checkpoints', 'routes-hit'];
// Rings at hour 0; HeatmapControls ("Show at ETA" on by default) moves them with the slider.
const ETA_FILTER_START = etaFilter(0);
const TRUCK_FILTER_START = truckFilter(0);

type PopupState =
  | { kind: 'checkpoint'; routeId: string; index: number }
  | { kind: 'route'; routeId: string; lng: number; lat: number }
  | null;

interface Props {
  plan: Plan | undefined;
  sidebarOffset: number;
}

export default function MapView({ plan, sidebarOffset }: Props) {
  const mapRef = useRef<MapRef>(null);
  const { state, dispatch } = useSelection();
  const [popup, setPopup] = useState<PopupState>(null);
  const [cursor, setCursor] = useState<string>('');
  const [iconReady, setIconReady] = useState(false);
  const selected = state.selectedRouteId;
  const hovered = state.hoveredRouteId;
  const HOVER: ExpressionSpecification = ['boolean', ['feature-state', 'hover'], false];

  const planId = plan?.id;
  const data = useMemo(() => {
    if (!plan) return null;
    return {
      lines: routeLines(plan),
      segments: riskSegments(plan),
      points: checkpointPoints(plan),
      trucks: truckPositions(plan),
      labels: routeLabels(plan, (id) => {
        const r = plan.routes.find((x) => x.id === id)!;
        const badge = r.is_recommended ? ' · Recommended' : '';
        return `${r.id} · ${formatDuration(r.duration_s)} · ${Math.round(r.summary.severe_mi)} severe mi${badge}`;
      }),
      bounds: bounds(plan),
    };
    // Rebuild only when the plan itself changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planId]);

  const heat = useHeatmap(plan?.id);
  const heatKey = heat.data ? `${heat.data.plan_id}:${heat.data.forecast_as_of}` : '';
  const heatData = useMemo(() => {
    if (!heat.data) return null;
    return {
      source: heatmapSource(heat.data),
      // Initial paint (hour 0, risk). Afterwards HeatmapControls swaps expressions
      // imperatively; these objects stay stable so React never resets them.
      heatPaint: {
        'heatmap-weight': weightExpression('risk', 0),
        'heatmap-radius': radiusExpression(heat.data.grid_step_deg),
        // Overlapping kernels roughly double density inside a uniform patch; 0.55 maps a
        // patch of level L back to density ≈ L/4 so the ramp colour matches the level.
        'heatmap-intensity': 0.55,
        'heatmap-color': HEAT_COLOR,
        'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 6.5, 0.85, 8, 0],
      } as Record<string, unknown>,
      cellPaint: {
        'circle-color': cellColorExpression('risk', 0),
        'circle-radius': ['interpolate', ['exponential', 2], ['zoom'], 7, 4, 10, 30],
        'circle-opacity': ['interpolate', ['linear'], ['zoom'], 6.5, 0, 8, 0.35],
        'circle-blur': 0.4,
      } as Record<string, unknown>,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heatKey]);

  // Fit all routes after planning, leaving room for the sidebar.
  useEffect(() => {
    if (!data) return;
    setPopup(null);
    mapRef.current?.fitBounds(data.bounds, {
      padding: { top: 64, bottom: 96, left: sidebarOffset + 48, right: 64 },
      duration: 800,
    });
  }, [data, sidebarOffset]);

  // Hover (from the map or a RouteCard) -> feature-state, so no paint prop or data changes.
  useEffect(() => {
    const map = mapRef.current?.getMap();
    const route = plan?.routes.find((r) => r.id === hovered);
    if (!map || !map.getSource('routes') || !route) return;
    const feature = { source: 'routes', id: route.rank }; // routeLines() uses rank as the id
    map.setFeatureState(feature, { hover: true });
    return () => {
      if (map.getSource('routes')) map.setFeatureState(feature, { hover: false });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hovered, planId]);

  // Sidebar table -> map: open the checkpoint popup when a row is clicked.
  useEffect(() => {
    const c = state.selectedCheckpoint;
    if (!c) return;
    setPopup({ kind: 'checkpoint', ...c });
    const cp = plan?.routes.find((r) => r.id === c.routeId)?.checkpoints[c.index];
    const map = mapRef.current;
    if (cp && map && !map.getBounds().contains([cp.lng, cp.lat])) {
      map.easeTo({ center: [cp.lng, cp.lat], duration: 500 });
    }
    // Only react to a new checkpoint selection.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.selectedCheckpoint]);

  const onClick = useCallback(
    (e: MapLayerMouseEvent) => {
      // A checkpoint under the cursor wins over the (wide, invisible) route hit line.
      const f = e.features?.find((x) => x.layer.id === 'checkpoints') ?? e.features?.[0];
      if (!f) {
        setPopup(null);
        return;
      }
      const p = f.properties as { routeId: string; index?: number };
      if (f.layer.id === 'checkpoints' && p.index !== undefined) {
        dispatch({ type: 'checkpoint', routeId: p.routeId, index: Number(p.index) });
      } else {
        dispatch({ type: 'select', routeId: p.routeId });
        setPopup({ kind: 'route', routeId: p.routeId, lng: e.lngLat.lng, lat: e.lngLat.lat });
      }
    },
    [dispatch],
  );

  const onMove = useCallback(
    (e: MapLayerMouseEvent) => {
      const f = e.features?.[0];
      setCursor(f ? 'pointer' : '');
      dispatch({ type: 'hover', routeId: f ? (f.properties as { routeId: string }).routeId : null });
    },
    [dispatch],
  );

  const isSel = (id: string | null): ExpressionSpecification => ['==', ['get', 'routeId'], id ?? ''];

  return (
    <Box sx={{ position: 'absolute', inset: 0 }}>
      <Map
        ref={mapRef}
        initialViewState={US_VIEW}
        mapStyle={STYLE_URL}
        interactiveLayerIds={data ? INTERACTIVE : []}
        onClick={onClick}
        onMouseMove={onMove}
        onMouseLeave={() => dispatch({ type: 'hover', routeId: null })}
        cursor={cursor}
        onLoad={(e) => {
          addTruckIcon(e.target);
          setIconReady(true); // the truck layer mounts only once its icon exists
        }}
        attributionControl={false}
        style={{ width: '100%', height: '100%' }}
      >
        <AttributionControl compact position="bottom-left" />
        <NavigationControl position="top-right" showCompass={false} />
        {data && (
          <>
            <Source id="routes" type="geojson" data={data.lines}>
              {/* Casing + base line for every route; selected/hovered drawn wider. */}
              <Layer
                id="routes-casing"
                type="line"
                layout={{ 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': ['-', 10, ['get', 'rank']] }}
                paint={{
                  'line-color': '#FFFFFF',
                  'line-width': ['case', isSel(selected), 10, HOVER, 8, 6],
                }}
              />
              <Layer
                id="routes-base"
                type="line"
                layout={{ 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': ['-', 10, ['get', 'rank']] }}
                paint={{
                  'line-color': ['case', HOVER, '#55636E', '#8A97A1'],
                  'line-width': ['case', isSel(selected), 6, HOVER, 5, 3],
                  'line-opacity': ['case', isSel(selected), 1, 0.85],
                }}
              />
              {/* Invisible wide line: easy to hover/click. */}
              <Layer
                id="routes-hit"
                type="line"
                paint={{ 'line-color': '#000', 'line-opacity': 0, 'line-width': 16 }}
              />
            </Source>
            <Source id="risk" type="geojson" data={data.segments}>
              <Layer
                id="risk-selected"
                type="line"
                filter={isSel(selected)}
                layout={{ 'line-join': 'round', 'line-cap': 'round' }}
                paint={{
                  'line-color': levelColorExpression() as ExpressionSpecification,
                  'line-width': 5,
                }}
              />
            </Source>
            <Source id="checkpoints" type="geojson" data={data.points}>
              <Layer
                id="checkpoints"
                type="circle"
                paint={{
                  'circle-color': levelColorExpression() as ExpressionSpecification,
                  'circle-radius': [
                    'interpolate', ['linear'], ['zoom'],
                    4, ['case', isSel(selected), 4, 2.5],
                    10, ['case', isSel(selected), 8, 5],
                  ],
                  'circle-stroke-color': '#FFFFFF',
                  'circle-stroke-width': ['case', isSel(selected), 1.5, 0.75],
                  'circle-opacity': ['case', isSel(selected), 1, 0.55],
                  'circle-stroke-opacity': ['case', isSel(selected), 1, 0.55],
                }}
              />
              {/* Ring around checkpoints the truck reaches in the slider's hour. */}
              <Layer
                id="checkpoints-eta"
                type="circle"
                filter={ETA_FILTER_START}
                paint={{
                  'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 8, 10, 14],
                  'circle-color': 'rgba(0,0,0,0)',
                  'circle-stroke-color': '#14212B',
                  'circle-stroke-width': 2.5,
                }}
              />
            </Source>
            {/* One truck per route at the slider's hour ("Show at ETA"). */}
            {iconReady && (
              <Source id="trucks" type="geojson" data={data.trucks}>
                <Layer
                  id="trucks"
                  type="symbol"
                  filter={TRUCK_FILTER_START}
                  layout={{
                    'icon-image': TRUCK_ICON,
                    'icon-size': ['interpolate', ['linear'], ['zoom'], 3, 0.8, 8, 1.1],
                    'icon-allow-overlap': true,
                    'icon-ignore-placement': true,
                  }}
                />
              </Source>
            )}
            <Source id="labels" type="geojson" data={data.labels}>
              <Layer
                id="route-labels"
                type="symbol"
                layout={{
                  'text-field': ['get', 'text'],
                  'text-font': ['Noto Sans Bold'],
                  'text-size': 12,
                  'text-offset': [0, -1.2],
                  'text-allow-overlap': false,
                  'text-padding': 4,
                  'text-max-width': 40,
                }}
                paint={{
                  'text-color': ['case', ['get', 'recommended'], '#0B3C49', '#37474F'],
                  'text-halo-color': '#FFFFFF',
                  'text-halo-width': 2,
                }}
              />
            </Source>
          </>
        )}
        {/* Rendered after the route layers so its beforeId ("routes-casing") always exists:
            the heatmap is drawn underneath the routes even when both arrive in one render. */}
        {data && heatData && (
          <Source id="heat" type="geojson" data={heatData.source}>
            <Layer id="heat" type="heatmap" beforeId="routes-casing" paint={heatData.heatPaint} />
            <Layer id="heat-cells" type="circle" beforeId="routes-casing" minzoom={6.5} paint={heatData.cellPaint} />
          </Source>
        )}
        {plan && (
          <HeatmapControls
            key={plan.id}
            start={heat.data?.start ?? plan.depart_at}
            hours={heat.data?.hours ?? 49}
            ready={Boolean(heatData)}
            loading={heat.isLoading}
            error={heat.isError ? errorMessage(heat.error) : null}
            onRetry={() => heat.refetch()}
          />
        )}
        {plan && popup?.kind === 'checkpoint' && (
          <CheckpointPopup plan={plan} routeId={popup.routeId} index={popup.index} onClose={() => {
            setPopup(null);
            dispatch({ type: 'clearCheckpoint' });
          }} />
        )}
        {plan && popup?.kind === 'route' && (
          <Popup
            longitude={popup.lng}
            latitude={popup.lat}
            onClose={() => setPopup(null)}
            closeOnClick={false} // the map click handler below opens/closes popups
            maxWidth="300px"
          >
            <RoutePopup route={plan.routes.find((r) => r.id === popup.routeId)!} />
          </Popup>
        )}
      </Map>
      {plan && (
        <Box
          sx={{
            position: 'absolute',
            pointerEvents: 'none',
            // Top-left: clear of the zoom buttons (top-right) and the slider (bottom).
            top: { xs: 8, md: 12 },
            left: { xs: 8, md: 12 },
            display: 'flex',
          }}
        >
          <Box sx={{ display: { xs: 'none', md: 'block' } }}>
            <Legend />
          </Box>
          <Box sx={{ display: { xs: 'block', md: 'none' }, mr: 6 }}>
            <Legend compact />
          </Box>
        </Box>
      )}
    </Box>
  );
}
