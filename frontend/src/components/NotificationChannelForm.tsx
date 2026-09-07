import { type FormEvent, useState } from 'react'
import { Button, SelectNative, TextInput } from 'react95'
import { Field, FieldError, FormActions, FormFields, FormPanel } from './FormPanel'
import { describeNonFieldError, extractFieldErrors } from '../api/errors'
import { useCreateNotificationChannel } from '../api/notificationChannels'
import type { NotificationChannelType } from '../api/types'

const TYPE_OPTIONS: { label: string; value: NotificationChannelType }[] = [
  { label: 'Email', value: 'EMAIL' },
  { label: 'Telegram', value: 'TELEGRAM' },
]

interface NotificationChannelFormProps {
  onCreated: () => void
  onCancel: () => void
}

export function NotificationChannelForm({ onCreated, onCancel }: NotificationChannelFormProps) {
  const [name, setName] = useState('')
  const [type, setType] = useState<NotificationChannelType>('EMAIL')
  const [email, setEmail] = useState('')
  const [chatId, setChatId] = useState('')

  const createChannel = useCreateNotificationChannel()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    createChannel.mutate(
      {
        name,
        type,
        // Mirrors NotificationChannelSerializer.validate on the backend:
        // EMAIL needs an 'email' key, TELEGRAM needs a 'chat_id' key.
        config: type === 'EMAIL' ? { email } : { chat_id: chatId },
      },
      { onSuccess: onCreated },
    )
  }

  const fieldErrors = extractFieldErrors(createChannel.error)
  const generalError = describeNonFieldError(createChannel.error)

  return (
    <FormPanel title="New notification channel">
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
          Type
          <SelectNative
            options={TYPE_OPTIONS}
            value={type}
            onChange={(option) => setType(option.value as NotificationChannelType)}
          />
        </Field>

        {type === 'EMAIL' ? (
          <Field>
            Email address
            <TextInput
              name="email"
              type="email"
              fullWidth
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </Field>
        ) : (
          <Field>
            Telegram chat ID
            <TextInput
              name="chat_id"
              fullWidth
              value={chatId}
              onChange={(event) => setChatId(event.target.value)}
              required
            />
          </Field>
        )}
        {fieldErrors.config && <FieldError role="alert">{fieldErrors.config}</FieldError>}

        {generalError && <FieldError role="alert">{generalError}</FieldError>}

        <FormActions>
          <Button type="submit" disabled={createChannel.isPending}>
            {createChannel.isPending ? 'Creating…' : 'Create channel'}
          </Button>
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
        </FormActions>
      </FormFields>
    </FormPanel>
  )
}
