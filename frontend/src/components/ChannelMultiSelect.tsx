import { Checkbox } from 'react95'
import type { NotificationChannel } from '../api/types'

interface ChannelMultiSelectProps {
  channels: NotificationChannel[]
  selectedIds: string[]
  onChange: (ids: string[]) => void
}

// A checkbox list rather than a native <select multiple> — react95 has no
// multiselect widget, and checkboxes are the more usable pattern for a
// handful of items anyway (no ctrl/cmd-click discoverability problem).
export function ChannelMultiSelect({ channels, selectedIds, onChange }: ChannelMultiSelectProps) {
  if (channels.length === 0) {
    return <p>No notification channels yet — create one on the Channels page to attach it here.</p>
  }

  function toggle(id: string) {
    onChange(
      selectedIds.includes(id)
        ? selectedIds.filter((existing) => existing !== id)
        : [...selectedIds, id],
    )
  }

  return (
    <fieldset>
      <legend>Notification channels</legend>
      {channels.map((channel) => (
        <Checkbox
          key={channel.id}
          label={`${channel.name} (${channel.type})`}
          checked={selectedIds.includes(channel.id)}
          onChange={() => toggle(channel.id)}
        />
      ))}
    </fieldset>
  )
}
