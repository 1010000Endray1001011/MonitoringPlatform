import { beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from './store'

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.getState().clearAccessToken()
  })

  it('starts with no access token', () => {
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('stores and clears a token', () => {
    useAuthStore.getState().setAccessToken('token-123')
    expect(useAuthStore.getState().accessToken).toBe('token-123')

    useAuthStore.getState().clearAccessToken()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})
