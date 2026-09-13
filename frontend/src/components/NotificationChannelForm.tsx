import { type FormEvent, useState } from 'react'
import { Button, SelectNative, TextInput } from 'react95'
import { Field, FieldError, FieldHint, FormActions, FormFields, FormPanel } from './FormPanel'
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
  const [telegramUsername, setTelegramUsername] = useState('')

  const createChannel = useCreateNotificationChannel()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    createChannel.mutate(
      {
        name,
        type,
        // Mirrors NotificationChannelSerializer.validate on the backend.
        // A Telegram channel carries no chat_id at this point and the API
        // would ignore one anyway — the id is assigned by the connect
        // handshake, from an update Telegram itself delivered. The
        // username is optional and only used to cross-check who presses
        // Start.
        config:
          type === 'EMAIL' ? { email } : telegramUsername ? { username: telegramUsername } : {},
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
          <>
            <Field>
              Telegram username
              <TextInput
                name="username"
                fullWidth
                value={telegramUsername}
                onChange={(event) => setTelegramUsername(event.target.value)}
                placeholder="@yourname"
              />
            </Field>
            <FieldHint>
              Optional. After creating the channel you'll get a one-time link — open it and press
              Start in the bot to connect this chat. If you fill this in, only that account can use
              the link.
            </FieldHint>
          </>
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
