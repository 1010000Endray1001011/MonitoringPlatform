import { type FormEvent, useState } from 'react'
import { Button, SelectNative, TextInput, Window, WindowContent, WindowHeader } from 'react95'
import { describeNonFieldError, extractFieldErrors } from '../api/errors'
import { useUpdateMonitor } from '../api/monitorDetail'
import { useNotificationChannels } from '../api/notificationChannels'
import type { MonitorDetail, MonitorInterval, MonitorMethod } from '../api/types'
import { ChannelMultiSelect } from './ChannelMultiSelect'
import { INTERVAL_OPTIONS, METHOD_OPTIONS } from './monitorFormOptions'

interface MonitorEditFormProps {
  monitor: MonitorDetail
  onSaved: () => void
  onCancel: () => void
}

// Full-payload PATCH, not a diff of changed fields — every editable field
// starts out at its current value, so submitting unmodified fields back
// as-is is harmless and this avoids dirty-field tracking for a form this
// small.
export function MonitorEditForm({ monitor, onSaved, onCancel }: MonitorEditFormProps) {
  const [name, setName] = useState(monitor.name)
  const [url, setUrl] = useState(monitor.url)
  const [method, setMethod] = useState<MonitorMethod>(monitor.method)
  const [expectedStatus, setExpectedStatus] = useState(monitor.expected_status)
  const [intervalSeconds, setIntervalSeconds] = useState<MonitorInterval>(monitor.interval_seconds)
  const [timeoutSeconds, setTimeoutSeconds] = useState(monitor.timeout_seconds)
  const [channelIds, setChannelIds] = useState<string[]>(
    monitor.notification_channels.map((channel) => channel.id),
  )

  const updateMonitor = useUpdateMonitor(monitor.id)
  const channels = useNotificationChannels()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    updateMonitor.mutate(
      {
        name,
        url,
        method,
        expected_status: expectedStatus,
        interval_seconds: intervalSeconds,
        timeout_seconds: timeoutSeconds,
        notification_channel_ids: channelIds,
      },
      { onSuccess: onSaved },
    )
  }

  const fieldErrors = extractFieldErrors(updateMonitor.error)
  const generalError = describeNonFieldError(updateMonitor.error)

  return (
    <Window>
      <WindowHeader>Edit monitor</WindowHeader>
      <WindowContent>
        <form onSubmit={handleSubmit}>
          <label>
            Name
            <TextInput
              name="name"
              fullWidth
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
          </label>
          {fieldErrors.name && <p role="alert">{fieldErrors.name}</p>}

          <label>
            URL
            <TextInput
              name="url"
              type="url"
              fullWidth
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              required
            />
          </label>
          {fieldErrors.url && <p role="alert">{fieldErrors.url}</p>}

          <label>
            Method
            <SelectNative
              options={METHOD_OPTIONS}
              value={method}
              onChange={(option) => setMethod(option.value as MonitorMethod)}
            />
          </label>

          <label>
            Expected status code
            {/* react95's NumberInput only ever calls onChange from its
                increment/decrement buttons — for a controlled instance
                (value + onChange, the only sane way to use it), its
                internal useControlledOrUncontrolled hook makes the
                typed-input handler a no-op, so typing a value does
                nothing at all. TextInput type="number" is the same
                underlying primitive NumberInput itself wraps, minus the
                broken bridge. */}
            <TextInput
              type="number"
              min={100}
              max={599}
              value={expectedStatus}
              onChange={(event) => setExpectedStatus(Number(event.target.value))}
            />
          </label>
          {fieldErrors.expected_status && <p role="alert">{fieldErrors.expected_status}</p>}

          <label>
            Check interval
            <SelectNative
              options={INTERVAL_OPTIONS}
              value={String(intervalSeconds)}
              onChange={(option) => setIntervalSeconds(Number(option.value) as MonitorInterval)}
            />
          </label>

          <label>
            Timeout (seconds)
            <TextInput
              type="number"
              min={1}
              max={30}
              value={timeoutSeconds}
              onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
            />
          </label>
          {fieldErrors.timeout_seconds && <p role="alert">{fieldErrors.timeout_seconds}</p>}

          <ChannelMultiSelect
            channels={channels.data?.results ?? []}
            selectedIds={channelIds}
            onChange={setChannelIds}
          />

          {generalError && <p role="alert">{generalError}</p>}

          <Button type="submit" disabled={updateMonitor.isPending}>
            {updateMonitor.isPending ? 'Saving…' : 'Save changes'}
          </Button>
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
        </form>
      </WindowContent>
    </Window>
  )
}
