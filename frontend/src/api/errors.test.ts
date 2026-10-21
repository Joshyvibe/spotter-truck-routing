import { ApiError } from './client';
import { errorMessage } from './errors';

describe('errorMessage', () => {
  it('uses friendly copy for known codes', () => {
    expect(errorMessage(new ApiError(502, 'UPSTREAM_UNAVAILABLE', 'raw'))).toMatch(/not responding/);
    expect(errorMessage(new ApiError(429, 'RATE_LIMITED', 'raw'))).toMatch(/wait a moment/);
  });

  it('keeps specific server messages for validation and geocoding', () => {
    expect(errorMessage(new ApiError(422, 'GEOCODE_NOT_FOUND', 'Could not find “Atlantis”.'))).toBe(
      'Could not find “Atlantis”.',
    );
  });

  it('falls back for unknown errors', () => {
    expect(errorMessage(new Error('x'))).toMatch(/went wrong/);
  });
});

describe('isRetryable', () => {
  it('follows the server flag', async () => {
    const { isRetryable } = await import('./errors');
    expect(isRetryable(new ApiError(502, 'UPSTREAM_UNAVAILABLE', 'x', null, true))).toBe(true);
    expect(isRetryable(new ApiError(422, 'NO_ROUTE', 'x'))).toBe(false);
  });
});
