import type { ReactNode } from 'react'
import styled from 'styled-components'
import { GroupBox } from 'react95'

// The three forms (new monitor, edit monitor, new channel) each opened
// their own <Window> — which, now that every screen is itself a window,
// meant a titled window nested inside a titled window, sized by its own
// content rather than by anything around it. That's what made them look
// out of proportion next to the dashboard's cards.
//
// A GroupBox is the Win95 idiom for a titled group *inside* a window, and
// it's already what MonitorCard uses on the dashboard — so a form now
// reads as the same kind of object as a monitor card instead of as a
// stray second window.
//
// Capped well below the page width on purpose: the page is 960px because
// tables and cards need it, but a single-column form stretched that wide
// puts the label at one end of the screen and nothing at the other.
const Panel = styled(GroupBox)`
  max-width: 620px;
`

interface FormPanelProps {
  title: ReactNode
  children: ReactNode
}

export function FormPanel({ title, children }: FormPanelProps) {
  return <Panel label={title}>{children}</Panel>
}

export const FormFields = styled.form`
  display: flex;
  flex-direction: column;
  gap: 12px;
`

// Label above its control, both stretching to the form's width. `$compact`
// is for the two numeric fields — a status code and a timeout are three
// characters wide, and an input sized for a URL makes them look like a
// mistake.
export const Field = styled.label<{ $compact?: boolean }>`
  display: flex;
  flex-direction: column;
  gap: 4px;
  ${(props) => props.$compact && 'max-width: 190px;'}
`

// Kept a sibling of the field rather than a child of its <label>: text
// inside the label becomes part of the control's accessible name, so an
// error appearing would silently rename the input it describes.
export const FieldError = styled.p`
  margin: 0;
  font-weight: bold;
  color: #b30000;
`

export const FormActions = styled.div`
  display: flex;
  gap: 8px;
`
