import { useAuthStore } from '../auth/store'

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    super(`API request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

// Concurrent 401s (e.g. a page that fires several queries at once right as
// the access token expires) must not each kick off their own refresh call —
// that would race multiple attempts to rotate the same one-time-use refresh
// cookie, and only the first would actually succeed. Every caller within the
// same window instead shares this one in-flight request.
let refreshPromise: Promise<string | null> | null = null

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/token/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!response.ok) {
      useAuthStore.getState().clearAccessToken()
      return null
    }
    const data = (await response.json()) as { access: string }
    useAuthStore.getState().setAccessToken(data.access)
    return data.access
  })()

  try {
    return await refreshPromise
  } finally {
    refreshPromise = null
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
}

// Endpoints where a 401 means exactly what it says (bad credentials, no
// cookie) rather than "your session expired mid-request" — retrying these
// through the refresh flow would be nonsensical (there was never a session
// to refresh) and, worse, would turn a plain "wrong password" on the login
// form into an unwanted redirect away from the login page itself.
const AUTH_ENDPOINTS_WITHOUT_RETRY = new Set([
  '/api/v1/auth/token',
  '/api/v1/auth/token/refresh',
  '/api/v1/auth/register',
])

async function request<T>(
  path: string,
  options: RequestOptions = {},
  isRetry = false,
): Promise<T> {
  const accessToken = useAuthStore.getState().accessToken
  const headers = new Headers(options.headers)
  if (options.body !== undefined) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    // Carries the httpOnly refresh cookie on same-site requests to the API
    // origin — without this, the browser never attaches it, and every
    // refresh attempt would look like it has no cookie at all.
    credentials: 'include',
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (response.status === 401 && !isRetry && !AUTH_ENDPOINTS_WITHOUT_RETRY.has(path)) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      return request<T>(path, options, true)
    }
    // No session left to retry with — refreshAccessToken already cleared
    // the store. A full reload (not a router redirect) is deliberate: it
    // guarantees every bit of in-memory state from the dead session,
    // Query cache included, is gone before /login renders.
    window.location.assign('/login')
    throw new ApiError(401, null)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, body)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
