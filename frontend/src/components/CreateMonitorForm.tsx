import { type FormEvent, useState } from 'react'
import { Button, SelectNative, TextInput } from 'react95'
import { Field, FieldError, FieldHint, FormActions, FormFields, FormPanel } from './FormPanel'
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
  const [body, setBody] = useState('')
  const [expectedStatus, setExpectedStatus] = useState(200)
  const [intervalSeconds, setIntervalSeconds] = useState<MonitorInterval>(300)
  const [timeoutSeconds, setTimeoutSeconds] = useState(10)
  // Defaults mirror the model's own (2 failures to go DOWN, 1 success to
  // recover) so an untouched form submits exactly what the API would have
  // applied on its own.
  const [failureThreshold, setFailureThreshold] = useState(2)
  const [successThreshold, setSuccessThreshold] = useState(1)
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
        // Cleared rather than sent when the method can't carry a body:
        // the API rejects that combination, and the local state is kept so
        // switching back to POST before saving doesn't lose what was typed.
        body: method === 'POST' ? body : '',
        expected_status: expectedStatus,
        interval_seconds: intervalSeconds,
        timeout_seconds: timeoutSeconds,
        failure_threshold: failureThreshold,
        success_threshold: successThreshold,
        notification_channel_ids: channelIds,
      },
      { onSuccess: onCreated },
    )
  }

  const fieldErrors = extractFieldErrors(createMonitor.error)
  const generalError = describeGeneralError(createMonitor.error)

  return (
    <FormPanel title="New monitor">
      <FormFields onSubmit={handleSubmit}>
        <Field>
          Name
          <TextInput
            name="name"
            fullWidth
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </Field>
        {fieldErrors.name && <FieldError role="alert">{fieldErrors.name}</FieldError>}

        <Field>
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
        </Field>
        {fieldErrors.url && <FieldError role="alert">{fieldErrors.url}</FieldError>}

        <Field>
          Method
          <SelectNative
            options={METHOD_OPTIONS}
            value={method}
            onChange={(option) => setMethod(option.value as MonitorMethod)}
          />
        </Field>

        {/* Only for POST: the API rejects a body on GET/HEAD, since
            neither has defined semantics for one. Hidden rather than
            disabled so the form never offers a control whose only
            possible outcome is an error. */}
        {method === 'POST' && (
          <>
            <Field>
              Request body
              <TextInput
                name="body"
                multiline
                rows={5}
                value={body}
                onChange={(event) => setBody(event.target.value)}
                placeholder={'{"probe": true}'}
              />
            </Field>
            <FieldHint>
              Sent as-is, UTF-8. Content-Type defaults to application/json — set your own
              Content-Type in the headers to override it.
            </FieldHint>
          </>
        )}
        {fieldErrors.body && <FieldError role="alert">{fieldErrors.body}</FieldError>}

        <Field $compact>
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
        </Field>
        {fieldErrors.expected_status && (
          <FieldError role="alert">{fieldErrors.expected_status}</FieldError>
        )}

        <Field>
          Check interval
          <SelectNative
            options={INTERVAL_OPTIONS}
            value={String(intervalSeconds)}
            onChange={(option) => setIntervalSeconds(Number(option.value) as MonitorInterval)}
          />
        </Field>

        <Field $compact>
          Timeout (seconds)
          <TextInput
            type="number"
            min={1}
            max={30}
            value={timeoutSeconds}
            onChange={(event) => setTimeoutSeconds(Number(event.target.value))}
          />
        </Field>
        {fieldErrors.timeout_seconds && (
          <FieldError role="alert">{fieldErrors.timeout_seconds}</FieldError>
        )}

        <Field $compact>
          Failure threshold
          <TextInput
            type="number"
            min={1}
            max={10}
            value={failureThreshold}
            onChange={(event) => setFailureThreshold(Number(event.target.value))}
          />
        </Field>
        {/* Kept out of the <Field> label on purpose: label text becomes the
            input's accessible name, so a hint inside it would be read out as
            part of the field's name. */}
        <FieldHint>
          How many failed checks in a row before the monitor is marked DOWN and an incident opens.
          Above 1 this deliberately rides out a single blip, so the first failing check leaves the
          monitor UP — set it to 1 if you want incidents to open immediately.
        </FieldHint>
        {fieldErrors.failure_threshold && (
          <FieldError role="alert">{fieldErrors.failure_threshold}</FieldError>
        )}

        <Field $compact>
          Recovery threshold
          <TextInput
            type="number"
            min={1}
            max={10}
            value={successThreshold}
            onChange={(event) => setSuccessThreshold(Number(event.target.value))}
          />
        </Field>
        <FieldHint>
          How many successful checks in a row before it counts as UP again and the open incident
          resolves.
        </FieldHint>
        {fieldErrors.success_threshold && (
          <FieldError role="alert">{fieldErrors.success_threshold}</FieldError>
        )}

        <ChannelMultiSelect
          channels={channels.data?.results ?? []}
          selectedIds={channelIds}
          onChange={setChannelIds}
        />

        {generalError && <FieldError role="alert">{generalError}</FieldError>}

        <FormActions>
          <Button type="submit" disabled={createMonitor.isPending}>
            {createMonitor.isPending ? 'Creating…' : 'Create monitor'}
          </Button>
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
        </FormActions>
      </FormFields>
    </FormPanel>
  )
}
