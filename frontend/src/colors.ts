export const ROUTE_COLORS = [
  '#d12f2f', 
  '#2f6fd1',
  '#2fa45a', 
  '#e0912f',
  '#8a5fd1', 
  '#5f6b7a', 
  '#17a2b8', 
  '#c23b8a', 
]

export function supportColor(intervalId: number): string {
  return ROUTE_COLORS[(intervalId - 1) % ROUTE_COLORS.length]
}
