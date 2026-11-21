export function datesAllowSearch(fromDate: string, toDate: string): boolean {
  return !fromDate || !toDate || fromDate <= toDate
}

export function dateQueryParams(fromDate: string, toDate: string) {
  return { start_date: fromDate || undefined, end_date: toDate || undefined }
}
