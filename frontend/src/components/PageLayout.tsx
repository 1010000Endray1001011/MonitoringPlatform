import type { ReactNode } from 'react'
import styled from 'styled-components'
import { Window, WindowContent, WindowHeader } from 'react95'

// Every screen behind the nav bar rendered a bare <Window> with no layout
// around it, which put all of them flush against the top-left corner of a
// full-viewport desktop background. This is that missing layout, kept in
// one component so a new screen can't quietly reintroduce the problem.
//
// Deliberately NOT shared with AuthWindow despite the visual family
// resemblance: the auth dialog is short and fixed-height so it centers on
// both axes, while these screens hold lists that outgrow the viewport and
// must stay pinned to the top — vertically centering a scrolling page
// makes its top edge unreachable.
const Backdrop = styled.div`
  box-sizing: border-box;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 24px;
`

// Capped rather than fluid: monitor cards and the incident/channel tables
// stay readable at ~960px and start looking stretched past it. `width:
// 100%` under the cap is what lets it shrink on a narrower viewport
// instead of overflowing.
const MAX_WIDTHS = {
  default: 960,
  // The 404 holds one sentence and one button — at full width it reads as
  // a broken layout rather than a deliberate one, so it borrows the auth
  // dialog's width instead.
  compact: 420,
} as const

const Panel = styled(Window)<{ $maxWidth: number }>`
  width: 100%;
  max-width: ${(props) => props.$maxWidth}px;
`

// The screens had no vertical rhythm at all — nav bar, filters, tables and
// cards all sat flush against each other. Spacing every top-level child
// here rather than in each page keeps it uniform, and using margin (rather
// than making this a flex column with a gap) leaves each child's natural
// width alone, so buttons stay button-sized instead of stretching to fill
// the window.
const Content = styled(WindowContent)`
  > * + * {
    margin-top: 16px;
  }
`

interface PageLayoutProps {
  title: ReactNode
  children: ReactNode
  size?: keyof typeof MAX_WIDTHS
}

export function PageLayout({ title, children, size = 'default' }: PageLayoutProps) {
  return (
    <Backdrop>
      <Panel $maxWidth={MAX_WIDTHS[size]}>
        <WindowHeader>{title}</WindowHeader>
        <Content>{children}</Content>
      </Panel>
    </Backdrop>
  )
}
