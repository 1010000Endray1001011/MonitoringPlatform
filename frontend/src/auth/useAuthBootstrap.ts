import { useEffect, useState } from 'react'
import { refreshAccessToken } from '../api/client'
import { useAuthStore } from './store'

/**
 * Every fresh page load starts with no access token in memory (it's never
 * persisted — see store.ts), so a protected route can't just check
 * "is accessToken set?" on first render; it has to first ask the backend,
 * via the httpOnly refresh cookie, whether a valid session actually exists.
 * `ready` stays false for that one round trip so ProtectedRoute doesn't
 * flash a redirect to /login before the answer comes back.
 */
export function useAuthBootstrap() {
  const accessToken = useAuthStore((state) => state.accessToken)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (accessToken) {
      setReady(true)
      return
    }
    refreshAccessToken().finally(() => setReady(true))
    // Runs once on mount only. Re-running this whenever accessToken changes
    // would also fire it right after a successful login, refreshing a token
    // that was just issued a moment ago for no reason.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { ready, isAuthenticated: Boolean(accessToken) }
}
