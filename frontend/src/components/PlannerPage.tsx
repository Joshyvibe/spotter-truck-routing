import AddRounded from '@mui/icons-material/AddRounded';
import ListAltOutlined from '@mui/icons-material/ListAltOutlined';
import RouteOutlined from '@mui/icons-material/RouteOutlined';
import {
  Alert,
  AppBar,
  Box,
  Button,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Skeleton,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { useCreatePlan, usePlan } from '../hooks/queries';
import { CheckpointTable } from './CheckpointTable';
import { RecommendationAlert } from './RecommendationAlert';
import { RouteList } from './RouteList';
import { TripForm } from './TripForm';
import { errorMessage, isRetryable } from '../api/errors';
import { valuesFromPlan } from './validateTrip';
import { useSelection } from '../hooks/useSelection';
import { SIDEBAR_WIDTH } from '../theme';
import type { PlanRequest } from '../types';

// The map bundle is large; load it after the form has painted.
const MapView = lazy(() => import('./MapView'));

export default function PlannerPage() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const theme = useTheme();
  const mobile = useMediaQuery(theme.breakpoints.down('md'));
  const create = useCreatePlan();
  const planQuery = usePlan(planId);
  const plan = planQuery.data;
  const { state, dispatch } = useSelection();
  // Mobile only: the sidebar lives in a bottom Drawer (DESIGN §7). Open for a new trip,
  // closed when a plan is on screen so the map is visible.
  const [drawerOpen, setDrawerOpen] = useState(!planId);
  // The same page instance serves "/" and "/plans/:id", so react to the route changing.
  useEffect(() => {
    if (!planId) setDrawerOpen(true); // "New trip": show the form (mobile)
  }, [planId]);
  useEffect(() => {
    if (create.isError) setDrawerOpen(true); // the error message lives in the drawer
  }, [create.isError]);

  // New plan -> select the recommended route.
  useEffect(() => {
    if (plan) dispatch({ type: 'reset', routeId: plan.recommended_route_id });
  }, [plan, dispatch]);

  const { mutate, reset } = create;
  const newTrip = useCallback(() => {
    reset(); // a previous failed submission's error must not follow into the fresh form
    navigate('/');
  }, [reset, navigate]);
  const submit = useCallback(
    (req: PlanRequest) =>
      mutate(req, {
        onSuccess: (p) => {
          setDrawerOpen(false);
          navigate(`/plans/${p.id}`);
          reset(); // back to idle so the new plan's results show
        },
      }),
    [mutate, reset, navigate],
  );
  const initial = useMemo(() => (plan ? valuesFromPlan(plan) : undefined), [plan]);
  const onSelect = useCallback((id: string) => dispatch({ type: 'select', routeId: id }), [dispatch]);
  const onHover = useCallback((id: string | null) => dispatch({ type: 'hover', routeId: id }), [dispatch]);

  const selectedRoute = plan?.routes.find((r) => r.id === state.selectedRouteId) ?? plan?.routes[0];
  const loading = create.isPending || (planQuery.isLoading && Boolean(planId));

  const sidebar = (
    <Stack spacing={2} sx={{ p: 2 }}>
      <TripForm
        key={plan?.id ?? 'new'}
        initial={initial}
        submitting={create.isPending}
        serverError={create.error}
        onSubmit={submit}
      />
      {create.isError && !(create.error as { field?: string }).field && (
        <Alert
          severity="error"
          action={
            isRetryable(create.error) && create.variables ? (
              <Button color="inherit" size="small" onClick={() => submit(create.variables!)}>
                Retry
              </Button>
            ) : undefined
          }
        >
          {errorMessage(create.error)}
        </Alert>
      )}
      {planQuery.isError && (
        <Alert
          severity="error"
          action={<Button color="inherit" size="small" onClick={() => planQuery.refetch()}>Retry</Button>}
        >
          {errorMessage(planQuery.error)}
        </Alert>
      )}
      {loading && (
        <Stack spacing={1.5} aria-busy="true" aria-label="Loading routes">
          <Skeleton variant="rounded" height={56} />
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} variant="rounded" height={148} />
          ))}
        </Stack>
      )}
      {plan && create.isIdle && (
        <>
          <Divider />
          <RecommendationAlert plan={plan} />
          <Typography variant="overline" color="text.secondary">
            Route options
          </Typography>
          <RouteList
            routes={plan.routes}
            selectedId={selectedRoute?.id}
            hoveredId={state.hoveredRouteId}
            onSelect={onSelect}
            onHover={onHover}
          />
          {selectedRoute && (
            <>
              <Typography variant="overline" color="text.secondary">
                {selectedRoute.label} checkpoints · every {plan.interval_mi} mi
              </Typography>
              <CheckpointTable
                route={selectedRoute}
                selectedIndex={
                  state.selectedCheckpoint?.routeId === selectedRoute.id
                    ? state.selectedCheckpoint.index
                    : null
                }
                onSelect={(index) => {
                  dispatch({ type: 'checkpoint', routeId: selectedRoute.id, index });
                  setDrawerOpen(false); // mobile: show the checkpoint popup on the map
                }}
              />
            </>
          )}
        </>
      )}
    </Stack>
  );

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="static" color="primary">
        <Toolbar variant="dense" sx={{ gap: 1 }}>
          <RouteOutlined />
          <Typography variant="h6" component="h1" noWrap sx={{ fontSize: 17 }}>
            {mobile ? 'Truck Routing' : 'Weather-Aware Truck Routing'}
          </Typography>
          <Box sx={{ flex: 1 }} />
          {mobile ? (
            <>
              {plan && (
                <IconButton color="inherit" aria-label="New trip" onClick={newTrip}>
                  <AddRounded />
                </IconButton>
              )}
              <IconButton
                color="inherit"
                aria-label="Show trip and routes"
                onClick={() => setDrawerOpen(true)}
              >
                <ListAltOutlined />
              </IconButton>
            </>
          ) : (
            plan && (
              <Button color="inherit" size="small" onClick={newTrip}>
                New trip
              </Button>
            )
          )}
        </Toolbar>
      </AppBar>
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
        }}
      >
        {!mobile && (
          <Box
            component="aside"
            sx={{
              width: SIDEBAR_WIDTH,
              flexShrink: 0,
              overflowY: 'auto',
              borderRight: 1,
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            {sidebar}
          </Box>
        )}
        <Box
          component="main"
          sx={{ position: 'relative', flex: 1, minWidth: 0 }}
        >
          <Suspense
            fallback={
              <Box sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
                <CircularProgress />
              </Box>
            }
          >
            {/* Same rule as the sidebar: never show an older plan under a new submission. */}
            <MapView plan={create.isIdle ? plan : undefined} sidebarOffset={0} />
            {!plan && !loading && (
              <Paper
                sx={{
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  maxWidth: 360,
                  p: 2,
                  border: 1,
                  borderColor: 'divider',
                  pointerEvents: 'none',
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  Enter a trip to compare 3 truck routes by the forecast at the truck&apos;s ETA
                  at each checkpoint, your load weight and travel time.
                </Typography>
              </Paper>
            )}
          </Suspense>
        </Box>
      </Box>
      {mobile && (
        <Drawer
          anchor="bottom"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          ModalProps={{ keepMounted: true }}
          PaperProps={{
            component: 'aside',
            sx: { maxHeight: '85vh', borderTopLeftRadius: 12, borderTopRightRadius: 12 },
          }}
        >
          {sidebar}
        </Drawer>
      )}
    </Box>
  );
}
