import type { FindRoutesParams } from './api/subtrajectories'
import type { Route } from './types'

export type SearchResult = {
  id: number
  query: FindRoutesParams
  routes: Route[]
}

export type RouteRef = {
  searchId: number
  index: number
}

export function routeKey(ref: RouteRef): string {
  return `${ref.searchId}:${ref.index}`
}

export function isRouteVisible(ref: RouteRef, checkedRoutes: Set<string>): boolean {
  return checkedRoutes.size === 0 || checkedRoutes.has(routeKey(ref))
}

export function sameRoute(a: RouteRef | null, b: RouteRef | null): boolean {
  return a !== null && b !== null && a.searchId === b.searchId && a.index === b.index
}

function formatDate(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function describeRange(from: string, to: string, format: (value: string) => string): string | null {
  if (from && to) return from === to ? format(from) : `${format(from)} – ${format(to)}`
  if (from) return `from ${format(from)}`
  if (to) return `until ${format(to)}`
  return null
}

export type Constraint = {
  label: string
  value: string
}

// The settings a search was run with, shown under its title when comparing searches.
export function searchConstraints(search: SearchResult): Constraint[] {
  const { fromDate, toDate, fromHour, toHour, epsilon } = search.query
  return [
    { label: 'Dates', value: describeRange(fromDate, toDate, formatDate) ?? 'All dates' },
    { label: 'Daily hours', value: describeRange(fromHour, toHour, (time) => time) ?? 'All day' },
    { label: 'Grouping distance', value: `${epsilon} m` },
  ]
}

export function meetsMinimum(route: Route, minSubtrajectories: number): boolean {
  return route.members.length >= minSubtrajectories
}

export function filterRoutes(routes: Route[], minSubtrajectories: number): Route[] {
  return routes.filter((route) => meetsMinimum(route, minSubtrajectories))
}

export function totalSubtrajectories(routes: Route[]): number {
  return routes.reduce((sum, route) => sum + route.members.length, 0)
}
