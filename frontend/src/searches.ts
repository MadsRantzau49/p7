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

export function searchLabel(search: SearchResult): string {
  const { fromDate, toDate, fromHour, toHour } = search.query
  const parts = [
    describeRange(fromDate, toDate, formatDate),
    describeRange(fromHour, toHour, (time) => time),
  ].filter((part): part is string => part !== null)
  if (parts.length === 0) return 'No constraints'
  const label = parts.join(' · ')
  return label.charAt(0).toUpperCase() + label.slice(1)
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
