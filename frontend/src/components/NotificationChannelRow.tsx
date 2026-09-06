import { useState } from 'react'
import { Button, TableDataCell, TableRow } from 'react95'
import { extractFieldErrors } from '../api/errors'
import {
  useDeleteNotificationChannel,
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
      <TableDataCell>{channel.is_verified ? 'Verified' : 'Not verified'}</TableDataCell>
      <TableDataCell>
        <Button onClick={() => verify.mutate()} disabled={verify.isPending}>
          {verifyLabel()}
        </Button>
        {verifyError && <p role="alert">{verifyError}</p>}
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
