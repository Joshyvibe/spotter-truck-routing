import type { ApiErrorBody, Heatmap, Place, Plan, PlanRequest } from '../types';

const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '') + '/api/v1';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly field: string | null = null,
    readonly retryable = false,
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError(0, 'NETWORK', 'Cannot reach the server. Check your connection.', null, true);
  }
  if (res.ok) return (await res.json()) as T;
  let body: ApiErrorBody | null = null;
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    /* non-JSON error page, e.g. a proxy */
  }
  const e = body?.error;
  if (!e && res.status >= 500) {
    // No API error envelope: a proxy or gateway answered for us (the API is down or restarting).
    throw new ApiError(res.status, 'NETWORK', 'Cannot reach the server.', null, true);
  }
  throw new ApiError(
    res.status,
    e?.code ?? 'INTERNAL',
    e?.message ?? `Request failed (${res.status}).`,
    e?.field ?? null,
    e?.retryable ?? res.status >= 500,
    e?.request_id ?? res.headers.get('X-Request-ID'),
  );
}

export const api = {
  createPlan: (body: PlanRequest) =>
    request<Plan>('/plans', { method: 'POST', body: JSON.stringify(body) }),
  getPlan: (id: string) => request<Plan>(`/plans/${encodeURIComponent(id)}`),
  getHeatmap: (id: string) => request<Heatmap>(`/plans/${encodeURIComponent(id)}/heatmap`),
  geocode: (q: string, signal?: AbortSignal) =>
    request<{ data: Place[] }>(`/geocode?q=${encodeURIComponent(q)}&limit=5`, { signal }),
  /** Fire-and-forget warm-up: wakes a sleeping API instance (e.g. Railway App Sleeping) while the user types. */
  warmUp: () => fetch(BASE + '/health').catch(() => undefined),
};
