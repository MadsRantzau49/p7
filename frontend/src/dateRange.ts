export function datesAllowSearch(fromDate: string, toDate: string): boolean {
  return Boolean(fromDate && toDate)
}

export function dateQueryParams(fromDate: string, toDate: string) {
  return { start_date: fromDate, end_date: toDate }
}
