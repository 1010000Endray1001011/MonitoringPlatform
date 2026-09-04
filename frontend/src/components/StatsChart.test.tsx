import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatsChart } from './StatsChart'

describe('StatsChart', () => {
  it('shows a placeholder instead of an empty chart when there is no data', () => {
    render(<StatsChart series={[]} />)

    expect(screen.getByText(/no data for this period/i)).toBeInTheDocument()
  })

  it('renders without crashing when given real series data', () => {
    render(
      <StatsChart
        series={[
          {
            bucket: '2026-09-03T00:00:00Z',
            checks_total: 10,
            checks_failed: 0,
            avg_response_time_ms: 120,
            p95_response_time_ms: 180,
          },
        ]}
      />,
    )

    expect(screen.queryByText(/no data for this period/i)).not.toBeInTheDocument()
  })
})
