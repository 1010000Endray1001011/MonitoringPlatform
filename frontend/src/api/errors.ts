import { ApiError } from './client'

export type FieldErrors = Record<string, string>

// Pulls the first message per field out of the backend's
// {"error": {"details": {field: [messages]}}} envelope — used by every
// form that submits directly to a DRF serializer, so a field's error shows
// up next to that field instead of as one generic banner.
export function extractFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError)) return {}
  const details = (error.body as { error?: { details?: Record<string, string[]> } })?.error
    ?.details
  if (!details) return {}
  const result: FieldErrors = {}
  for (const [field, messages] of Object.entries(details)) {
    if (Array.isArray(messages) && typeof messages[0] === 'string') {
      result[field] = messages[0]
    }
  }
  return result
}

// Fallback for a 400 that didn't resolve to any per-field message (e.g. a
// non_field_errors-style validation, or details the shape above doesn't
// recognize) — better than showing nothing.
export function describeNonFieldError(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null
  if (error.status === 400 && Object.keys(extractFieldErrors(error)).length === 0) {
    return 'Please check the form and try again.'
  }
  return null
}
