// Thin re-export layer over the generated schema — every other file
// imports request/response shapes from here rather than reaching into
// schema.ts's `components["schemas"][...]` indexing directly, so a
// regeneration that changes the generated structure only needs fixing up
// in one place.
import type { components } from './schema'

export type AccessToken = components['schemas']['AccessToken']
export type TokenObtainPairRequest = components['schemas']['TokenObtainPairRequest']
export type RegisterRequest = components['schemas']['RegisterRequest']
export type RegisterResponse = components['schemas']['Register']

export type MonitorList = components['schemas']['MonitorList']
export type MonitorDetail = components['schemas']['MonitorDetail']
export type MonitorStatus = components['schemas']['MonitorStatus']
export type MonitorWriteRequest = components['schemas']['MonitorWriteRequest']
export type MonitorPatchRequest = components['schemas']['PatchedMonitorWriteRequest']
export type PaginatedMonitorList = components['schemas']['PaginatedMonitorListList']
export type MonitorMethod = components['schemas']['MethodEnum']
export type MonitorInterval = components['schemas']['IntervalSecondsEnum']

export type CheckResult = components['schemas']['CheckResult']
// Cursor-paginated, not page-based — no `count` field. See
// CheckResultCursorPageSerializer on the backend for why this needed a
// hand-written schema entry instead of being auto-detected.
export type CheckResultCursorPage = components['schemas']['CheckResultCursorPage']
export type ImmediateCheckAccepted = components['schemas']['ImmediateCheckAccepted']

export type MonitorStats = components['schemas']['MonitorStats']
export type PeriodSummary = components['schemas']['PeriodSummary']
export type StatsSeriesBucket = components['schemas']['StatsSeriesBucket']
export type StatsPeriod = '24h' | '7d' | '30d'
