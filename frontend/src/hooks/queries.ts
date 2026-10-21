import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { Plan, PlanRequest } from '../types';
import { ApiError, api } from '../api/client';

const TEN_MIN = 10 * 60 * 1000;

export const planKey = (id: string) => ['plan', id] as const;

export function usePlan(id: string | undefined) {
  return useQuery({
    queryKey: planKey(id ?? ''),
    queryFn: () => api.getPlan(id!),
    enabled: Boolean(id),
    staleTime: TEN_MIN, // matches the server-side caches
    retry: (count, err) => err instanceof ApiError && err.retryable && count < 1,
  });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PlanRequest) => api.createPlan(body),
    // Seed the cache so navigating to /plans/:id renders instantly with no refetch.
    onSuccess: (plan: Plan) => qc.setQueryData(planKey(plan.id), plan),
  });
}

export function useGeocode(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: ['geocode', query.toLowerCase()],
    queryFn: ({ signal }) => api.geocode(query, signal).then((r) => r.data),
    enabled: query.length >= 3,
    staleTime: TEN_MIN,
    retry: false,
  });
}

/** Starts as soon as a plan exists, so routes render first and the heatmap streams in. */
export function useHeatmap(planId: string | undefined) {
  return useQuery({
    queryKey: ['heatmap', planId ?? ''],
    queryFn: () => api.getHeatmap(planId!),
    enabled: Boolean(planId),
    staleTime: TEN_MIN,
    retry: (count, err) => err instanceof ApiError && err.retryable && count < 1,
  });
}
