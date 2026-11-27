const ROUTE_COLORS = [
  '#d12f2f',
  '#2f6fd1',
  '#2fa45a',
  '#e0912f',
  '#8a5fd1',
  '#5f6b7a',
  '#17a2b8',
  '#c23b8a',
]

const SEARCH_HUES = [0, 215, 135, 30, 275, 185, 325, 50]

const SHADES = [
  { saturation: 75, lightness: 45 },
  { saturation: 85, lightness: 28 },
  { saturation: 70, lightness: 62 },
  { saturation: 60, lightness: 36 },
  { saturation: 90, lightness: 52 },
  { saturation: 55, lightness: 22 },
  { saturation: 65, lightness: 72 },
  { saturation: 80, lightness: 40 },
]

function shade(searchPosition: number, routeIndex: number): string {
  const hue = SEARCH_HUES[searchPosition % SEARCH_HUES.length]
  const { saturation, lightness } = SHADES[routeIndex % SHADES.length]
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`
}

export function searchColor(searchPosition: number): string {
  return shade(searchPosition, 0)
}

export function routeColor(searchPosition: number, routeIndex: number, searchCount: number): string {
  if (searchCount <= 1) return ROUTE_COLORS[routeIndex % ROUTE_COLORS.length]
  return shade(searchPosition, routeIndex)
}
