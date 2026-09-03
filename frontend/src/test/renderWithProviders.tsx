import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppThemeProvider } from '../theme/AppThemeProvider'

// Every page needs the same three providers (routing, query cache, React95
// theme) — centralized here so a page test only has to think about what
// it's actually testing, not how to wire up the app shell around it.
export function renderWithProviders(ui: ReactElement, { route = '/' } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <AppThemeProvider>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AppThemeProvider>
    </QueryClientProvider>,
  )
}
