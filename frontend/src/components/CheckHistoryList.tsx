import {
  Button,
  Table,
  TableBody,
  TableDataCell,
  TableHead,
  TableHeadCell,
  TableRow,
} from 'react95'
import type { CheckResult } from '../api/types'

interface CheckHistoryListProps {
  checks: CheckResult[]
  hasMore: boolean
  isLoadingMore: boolean
  onLoadMore: () => void
}

export function CheckHistoryList({
  checks,
  hasMore,
  isLoadingMore,
  onLoadMore,
}: CheckHistoryListProps) {
  if (checks.length === 0) {
    return <p>No checks recorded yet.</p>
  }

  return (
    <>
      <Table>
        <TableHead>
          <TableRow>
            <TableHeadCell>Time</TableHeadCell>
            <TableHeadCell>Result</TableHeadCell>
            <TableHeadCell>Status</TableHeadCell>
            <TableHeadCell>Response time</TableHeadCell>
            <TableHeadCell>Error</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {checks.map((check) => (
            <TableRow key={check.id}>
              <TableDataCell>{new Date(check.checked_at).toLocaleString()}</TableDataCell>
              <TableDataCell>{check.success ? '✓' : '✗'}</TableDataCell>
              <TableDataCell>{check.status_code ?? '—'}</TableDataCell>
              <TableDataCell>
                {check.response_time_ms === null ? '—' : `${check.response_time_ms} ms`}
              </TableDataCell>
              <TableDataCell>{check.error_type ?? '—'}</TableDataCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {hasMore && (
        <Button onClick={onLoadMore} disabled={isLoadingMore}>
          {isLoadingMore ? 'Loading…' : 'Load more'}
        </Button>
      )}
    </>
  )
}
