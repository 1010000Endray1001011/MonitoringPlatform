import { useState } from 'react'
import { Button, Table, TableBody, TableHead, TableHeadCell, TableRow } from 'react95'
import { useNotificationChannels } from '../api/notificationChannels'
import { NavBar } from '../components/NavBar'
import { NotificationChannelForm } from '../components/NotificationChannelForm'
import { PageLayout } from '../components/PageLayout'
import { NotificationChannelRow } from '../components/NotificationChannelRow'

export function ChannelsPage() {
  const [showCreateForm, setShowCreateForm] = useState(false)
  const channels = useNotificationChannels()

  return (
    <PageLayout title="Notification channels">
      <NavBar />

      {showCreateForm ? (
        <NotificationChannelForm
          onCreated={() => setShowCreateForm(false)}
          onCancel={() => setShowCreateForm(false)}
        />
      ) : (
        <>
          <Button onClick={() => setShowCreateForm(true)}>New channel</Button>

          {channels.isLoading && <p>Loading…</p>}
          {channels.isError && <p role="alert">Couldn't load your channels. Try reloading.</p>}

          {channels.data && channels.data.results.length === 0 && (
            <p>
              You don't have any notification channels yet — create one so incidents can actually
              reach you.
            </p>
          )}

          {channels.data && channels.data.results.length > 0 && (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeadCell>Name</TableHeadCell>
                  <TableHeadCell>Type</TableHeadCell>
                  <TableHeadCell>Status</TableHeadCell>
                  <TableHeadCell>Verify</TableHeadCell>
                  <TableHeadCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {channels.data.results.map((channel) => (
                  <NotificationChannelRow key={channel.id} channel={channel} />
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </PageLayout>
  )
}
