import { ApiError } from './client';

/** Friendly copy per API error code. The server message is used when it is more specific. */
const COPY: Record<string, string> = {
  NO_ROUTE: 'No truck route was found between these places.',
  UPSTREAM_UNAVAILABLE: 'A routing or weather service is not responding. Please try again.',
  RATE_LIMITED: 'Too many plans in a short time. Please wait a moment and try again.',
  NETWORK: 'Cannot reach the server. Check your connection and try again.',
  PLAN_NOT_FOUND: 'This plan link is not valid or has expired.',
  INTERNAL: 'Something went wrong on our side. Please try again.',
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'VALIDATION' || err.code === 'GEOCODE_NOT_FOUND') return err.message;
    return COPY[err.code] ?? err.message;
  }
  return COPY.INTERNAL!;
}

export const isRetryable = (err: unknown) => err instanceof ApiError && err.retryable;
