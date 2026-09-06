import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import { Tab, TabBody, Tabs, Window, WindowContent, WindowHeader } from 'react95'

// Which route each tab maps to. The tabs are real navigation rather than
// local component state: /login and /register stay separate URLs, so both
// remain bookmarkable and the redirect after a successful registration
// still has a concrete place to send the user. The consequence worth
// knowing is that there is no "currently selected tab" value to keep in
// sync with anything — the route that rendered the page *is* the
// selection, so the two can never disagree.
const TAB_ROUTES = {
  login: '/login',
  register: '/register',
} as const

export type AuthTab = keyof typeof TAB_ROUTES

// Login and register are the only two screens that render with no NavBar
// and no other chrome around them, so under plain document flow the
// window ends up jammed into the top-left corner of an otherwise empty
// desktop. Centering lives here, once, rather than in each page —
// otherwise the two screens drift apart the first time one is touched on
// its own. box-sizing is set explicitly because the react95 style reset
// doesn't set a global one, and without it the padding below is added
// *on top of* 100vh and produces a scrollbar on a page that fits.
const Backdrop = styled.div`
  box-sizing: border-box;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
`

// Capped rather than fixed, so it still reads as a dialog on a wide
// monitor instead of stretching edge to edge, and `width: 100%` under
// that cap so it shrinks rather than overflowing a narrow viewport.
const Panel = styled(Window)`
  width: 100%;
  max-width: 420px;
`

// The two forms carried no spacing of their own — inputs and submit
// button sat flush against each other, which passed unnoticed in a
// cramped corner window and looks unfinished at this width. The gap lives
// here so both forms stay identically spaced without either page owning
// layout rules of its own.
export const AuthForm = styled.form`
  display: flex;
  flex-direction: column;
  gap: 12px;
`

// Both auth screens show the same kind of short, one-line feedback in the
// same slot: a red failure ("Incorrect email or password") or a neutral
// hand-off notice ("Account created — log in below"). Only the color
// distinguishes them, so they share one component rather than two that
// would have to be kept visually in step by hand.
export const AuthMessage = styled.p<{ $tone: 'error' | 'info' }>`
  margin: 0;
  font-weight: bold;
  color: ${(props) => (props.$tone === 'error' ? '#b30000' : 'inherit')};
`

interface AuthWindowProps {
  active: AuthTab
  children: ReactNode
}

export function AuthWindow({ active, children }: AuthWindowProps) {
  const navigate = useNavigate()

  return (
    <Backdrop>
      <Panel>
        <WindowHeader>Monitoring Platform</WindowHeader>
        <WindowContent>
          {/* react95 gives Tab an explicit role="tab", so these never
              collide with a getByRole('button') lookup for the submit
              button sitting a few lines below them with the same label. */}
          <Tabs value={active} onChange={(value) => navigate(TAB_ROUTES[value as AuthTab])}>
            <Tab value="login">Log in</Tab>
            <Tab value="register">Register</Tab>
          </Tabs>
          <TabBody>{children}</TabBody>
        </WindowContent>
      </Panel>
    </Backdrop>
  )
}
