import { create } from 'zustand'

interface AuthState {
  // In memory only, on purpose — never persisted to localStorage/sessionStorage.
  // Anything a script could read out of persistent storage after an XSS
  // injection is a token an attacker can steal; keeping it here means a page
  // reload always starts with this as null, and useAuthBootstrap re-derives
  // it from the httpOnly refresh cookie (which JS can't read at all) instead.
  accessToken: string | null
  setAccessToken: (token: string) => void
  clearAccessToken: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  setAccessToken: (token) => set({ accessToken: token }),
  clearAccessToken: () => set({ accessToken: null }),
}))
