import { type FormEvent, useState } from 'react'
import { Button, SelectNative, TextInput, Window, WindowContent, WindowHeader } from 'react95'
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
    <Window>
      <WindowHeader>New notification channel</WindowHeader>
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
            Type
            <SelectNative
              options={TYPE_OPTIONS}
              value={type}
              onChange={(option) => setType(option.value as NotificationChannelType)}
            />
          </label>

          {type === 'EMAIL' ? (
            <label>
              Email address
              <TextInput
                name="email"
                type="email"
                fullWidth
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
          ) : (
            <label>
              Telegram chat ID
              <TextInput
                name="chat_id"
                fullWidth
                value={chatId}
                onChange={(event) => setChatId(event.target.value)}
                required
              />
            </label>
          )}
          {fieldErrors.config && <p role="alert">{fieldErrors.config}</p>}

          {generalError && <p role="alert">{generalError}</p>}

          <Button type="submit" disabled={createChannel.isPending}>
            {createChannel.isPending ? 'Creating…' : 'Create channel'}
          </Button>
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
        </form>
      </WindowContent>
    </Window>
  )
}
