import { apiClient } from '../api/client'
import { useAuthStore } from './store'

export async function logout(): Promise<void> {
  try {
    await apiClient.post('/api/v1/auth/logout')
  } finally {
    // Cleared even if the request itself failed (e.g. offline) — there's
    // nothing server-side left to wait for once the client has decided to
    // forget its own access token; see LogoutView for why the cookie is
    // the only thing that call can actually revoke.
    useAuthStore.getState().clearAccessToken()
  }
}
