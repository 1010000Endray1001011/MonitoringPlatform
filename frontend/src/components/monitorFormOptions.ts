import type { MonitorMethod } from '../api/types'

export const METHOD_OPTIONS: { label: string; value: MonitorMethod }[] = [
  { label: 'GET', value: 'GET' },
  { label: 'HEAD', value: 'HEAD' },
  { label: 'POST', value: 'POST' },
]

// Mirrors Monitor.ALLOWED_INTERVALS on the backend — the API rejects
// anything outside this set with a 400, so offering only these values
// means the interval field can never be the reason a submission fails.
// SelectNative only supports string-valued options (unlike the generic
// Select component), hence string keys here rather than MonitorInterval —
// callers convert back to a number in their own onChange handler.
export const INTERVAL_OPTIONS: { label: string; value: string }[] = [
  { label: '1 minute', value: '60' },
  { label: '2 minutes', value: '120' },
  { label: '5 minutes', value: '300' },
  { label: '10 minutes', value: '600' },
  { label: '15 minutes', value: '900' },
  { label: '30 minutes', value: '1800' },
  { label: '1 hour', value: '3600' },
]
