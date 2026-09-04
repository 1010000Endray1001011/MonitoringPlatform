import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { StatsSeriesBucket } from '../api/types'

interface StatsChartProps {
  series: StatsSeriesBucket[]
}

// Response time only, not checks_failed — mixing a millisecond axis and a
// count axis on one chart needs a second Y axis and a legend explaining
// which line is which, which is more chart than this screen needs right
// now. Failures are already visible directly in the check history list
// below it.
export function StatsChart({ series }: StatsChartProps) {
  if (series.length === 0) {
    return <p>No data for this period yet.</p>
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={series}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
        <YAxis
          tick={{ fontSize: 11 }}
          label={{ value: 'ms', angle: -90, position: 'insideLeft' }}
        />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="avg_response_time_ms"
          name="Avg response time"
          stroke="#0033a0"
          dot={false}
          connectNulls
        />
        <Line
          type="monotone"
          dataKey="p95_response_time_ms"
          name="p95 response time"
          stroke="#b30000"
          dot={false}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
