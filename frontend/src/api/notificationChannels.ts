import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type {
  NotificationChannel,
  NotificationChannelWriteRequest,
  PaginatedNotificationChannelList,
} from './types'

// A single fixed key, unlike monitors/incidents — channels aren't filtered
// or searched anywhere in this app, so there's no params object to fold
// into the key.
export const channelsQueryKey = ['notification-channels'] as const

// A Telegram channel becomes connected without the browser doing anything:
// the user presses Start in the bot, and a background task on the server
// binds the chat. Polling while any channel is in that state is what turns
// the row from "waiting" into "verified" on its own — five seconds is short
// enough to feel immediate next to walking to your phone, and the polling
// stops the moment nothing is waiting.
const WAITING_POLL_MS = 5000

export function useNotificationChannels() {
  return useQuery({
    queryKey: channelsQueryKey,
    queryFn: () =>
      apiClient.get<PaginatedNotificationChannelList>('/api/v1/notification-channels/'),
    refetchInterval: (query) => {
      const waiting = (query.state.data?.results ?? []).some(
        (channel) =>
          channel.type === 'TELEGRAM' && !channel.is_verified && channel.telegram_deep_link,
      )
      return waiting ? WAITING_POLL_MS : false
    },
  })
}

export function useIssueTelegramLink(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiClient.post<NotificationChannel>(`/api/v1/notification-channels/${id}/telegram-link/`),
    // The response is the channel carrying its new link, so patch it into
    // the cached list rather than refetching the whole thing.
    onSuccess: (data) => {
      queryClient.setQueryData<PaginatedNotificationChannelList>(channelsQueryKey, (old) => {
        if (!old) return old
        return {
          ...old,
          results: old.results.map((channel) => (channel.id === data.id ? data : channel)),
        }
      })
    },
  })
}

export function useCreateNotificationChannel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: NotificationChannelWriteRequest) =>
      apiClient.post<NotificationChannel>('/api/v1/notification-channels/', body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: channelsQueryKey }),
  })
}

export function useDeleteNotificationChannel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/api/v1/notification-channels/${id}/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: channelsQueryKey }),
  })
}

export function useVerifyNotificationChannel(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiClient.post<NotificationChannel>(`/api/v1/notification-channels/${id}/verify/`),
    // Same reasoning as acknowledge: the response already carries the
    // updated is_verified/last_error, so patch the cached list with it
    // directly instead of refetching.
    onSuccess: (data) => {
      queryClient.setQueryData<PaginatedNotificationChannelList>(channelsQueryKey, (old) => {
        if (!old) return old
        return {
          ...old,
          results: old.results.map((channel) => (channel.id === data.id ? data : channel)),
        }
      })
    },
  })
}
