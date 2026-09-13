import { useState } from 'react'
import { Button, TableDataCell, TableRow } from 'react95'
import { Anchor } from 'react95'
import { extractFieldErrors } from '../api/errors'
import {
  useDeleteNotificationChannel,
  useIssueTelegramLink,
  useVerifyNotificationChannel,
} from '../api/notificationChannels'
import type { NotificationChannel } from '../api/types'

interface NotificationChannelRowProps {
  channel: NotificationChannel
}

export function NotificationChannelRow({ channel }: NotificationChannelRowProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const verify = useVerifyNotificationChannel(channel.id)
  const deleteChannel = useDeleteNotificationChannel()
  const issueLink = useIssueTelegramLink(channel.id)

  // A Telegram channel isn't verified by pressing a button here — it's
  // verified by the user pressing Start in the bot, which the server picks
  // up on its own. So until that happens the row offers the link instead of
  // a Verify button that could only ever fail.
  const awaitingConnect = channel.type === 'TELEGRAM' && !channel.is_verified

  // A failed verify is a real 400 (see verify_channel in the backend
  // service — it persists last_error server-side, then raises), not a 200
  // with is_verified: false. So the failure message comes straight off
  // the mutation's own error, not off the (still-stale-until-a-reload)
  // cached channel.
  const verifyError = extractFieldErrors(verify.error).config

  function verifyLabel(): string {
    if (verify.isPending) return 'Verifying…'
    if (verify.isSuccess) return 'Verified ✓'
    return 'Verify'
  }

  return (
    <TableRow>
      <TableDataCell>{channel.name}</TableDataCell>
      <TableDataCell>{channel.type}</TableDataCell>
      <TableDataCell>
        {channel.is_verified ? 'Verified' : awaitingConnect ? 'Waiting for Start' : 'Not verified'}
      </TableDataCell>
      <TableDataCell>
        {awaitingConnect ? (
          channel.telegram_deep_link ? (
            <Anchor href={channel.telegram_deep_link} target="_blank" rel="noopener noreferrer">
              Open bot and press Start
            </Anchor>
          ) : (
            // No link means the previous one expired (or no bot username is
            // configured server-side) — either way the way forward is a
            // fresh one, not a retry of something that no longer exists.
            <Button onClick={() => issueLink.mutate()} disabled={issueLink.isPending}>
              {issueLink.isPending ? 'Getting a link…' : 'Get a new link'}
            </Button>
          )
        ) : (
          <>
            <Button onClick={() => verify.mutate()} disabled={verify.isPending}>
              {verifyLabel()}
            </Button>
            {verifyError && <p role="alert">{verifyError}</p>}
          </>
        )}
      </TableDataCell>
      <TableDataCell>
        {confirmingDelete ? (
          <>
            <Button
              onClick={() => deleteChannel.mutate(channel.id)}
              disabled={deleteChannel.isPending}
            >
              {deleteChannel.isPending ? 'Deleting…' : 'Confirm delete'}
            </Button>
            <Button onClick={() => setConfirmingDelete(false)}>Cancel</Button>
          </>
        ) : (
          <Button onClick={() => setConfirmingDelete(true)}>Delete</Button>
        )}
      </TableDataCell>
    </TableRow>
  )
}
