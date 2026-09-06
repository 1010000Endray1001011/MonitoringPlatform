import { type FormEvent, useState } from 'react'
import {
  Button,
  NumberInput,
  SelectNative,
  TextInput,
  Window,
  WindowContent,
  WindowHeader,
} from 'react95'
import { ApiError } from '../api/client'
import { describeNonFieldError, extractFieldErrors } from '../api/errors'
import { useCreateMonitor } from '../api/monitors'
import { useNotificationChannels } from '../api/notificationChannels'
import type { MonitorInterval, MonitorMethod } from '../api/types'
import { ChannelMultiSelect } from './ChannelMultiSelect'
import { INTERVAL_OPTIONS, METHOD_OPTIONS } from './monitorFormOptions'

function describeGeneralError(error: unknown): string | null {
  if (error instanceof ApiError && error.status === 422) {
    return "You've reached your monitor quota. Remove a monitor or contact support to raise the limit."
  }
  return describeNonFieldError(error)
}

interface CreateMonitorFormProps {
  onCreated: () => void
  onCancel: () => void
}

export function CreateMonitorForm({ onCreated, onCancel }: CreateMonitorFormProps) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [method, setMethod] = useState<MonitorMethod>('GET')
  const [expectedStatus, setExpectedStatus] = useState(200)
  const [intervalSeconds, setIntervalSeconds] = useState<MonitorInterval>(300)
  const [timeoutSeconds, setTimeoutSeconds] = useState(10)
  const [channelIds, setChannelIds] = useState<string[]>([])

  const createMonitor = useCreateMonitor()
  const channels = useNotificationChannels()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    createMonitor.mutate(
      {
        name,
        url,
        method,
        expected_status: expectedStatus,
        interval_seconds: intervalSeconds,
        timeout_seconds: timeoutSeconds,
        notification_channel_ids: channelIds,
      },
      { onSuccess: onCreated },
    )
  }

  const fieldErrors = extractFieldErrors(createMonitor.error)
  const generalError = describeGeneralError(createMonitor.error)

  return (
    <Window>
      <WindowHeader>New monitor</WindowHeader>
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
              placeholder="https://example.com/health"
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
            <NumberInput min={100} max={599} value={expectedStatus} onChange={setExpectedStatus} />
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
            <NumberInput min={1} max={30} value={timeoutSeconds} onChange={setTimeoutSeconds} />
          </label>
          {fieldErrors.timeout_seconds && <p role="alert">{fieldErrors.timeout_seconds}</p>}

          <ChannelMultiSelect
            channels={channels.data?.results ?? []}
            selectedIds={channelIds}
            onChange={setChannelIds}
          />

          {generalError && <p role="alert">{generalError}</p>}

          <Button type="submit" disabled={createMonitor.isPending}>
            {createMonitor.isPending ? 'Creating…' : 'Create monitor'}
          </Button>
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
        </form>
      </WindowContent>
    </Window>
  )
}
