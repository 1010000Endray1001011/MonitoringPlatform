import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from '../api/mocks/server'

// One MSW server for the whole test run — individual tests add handlers
// via server.use() and everything resets between tests so one test's mock
// can never leak into the next.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
