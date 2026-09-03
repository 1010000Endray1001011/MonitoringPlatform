import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A monitoring dashboard's data goes stale the moment the next check
      // runs, which could be seconds away — an aggressive default TTL would
      // just be optimistic-caching that turns out to be wrong most of the
      // time. Individual queries opt into refetchInterval where live status
      // actually matters instead.
      staleTime: 0,
      retry: 1,
    },
  },
})
