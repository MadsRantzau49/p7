export const USAGE_COLORS = [
  '#ffd400', '#ed7800', '#cc101c', '#a30067', '#663399',
  '#153ea1', '#007e94', '#006b45', '#70411f', '#282828',
]
export const REPRESENTATIVE_COLOR = '#383838'
export const CONTRIBUTION_COLOR = '#000000'

export type UsageBand = { min: number; max: number; color: string }

// Round the band width up to 1, 2, 5 or 10 times a power of ten.
// For example, a maximum of 87 produces 1–10, 11–20, …, 81–87.
export function usageBands(maxCount: number): UsageBand[] {
  const maximum = Math.max(1, Math.ceil(maxCount))
  const target = maximum / USAGE_COLORS.length
  const magnitude = 10 ** Math.floor(Math.log10(target))
  const multiple = [1, 2, 5, 10].find(value => value * magnitude >= target)!
  const width = Math.max(1, Math.ceil(multiple * magnitude))
  return Array.from({ length: Math.ceil(maximum / width) }, (_, index) => ({
    min: index * width + 1,
    max: Math.min((index + 1) * width, maximum),
    color: USAGE_COLORS[index],
  }))
}

export function usageColor(count: number, maxCount: number): string {
  const bands = usageBands(maxCount)
  return (bands.find(band => count <= band.max) ?? bands[bands.length - 1]).color
}

const JOURNEY_COLORS = [
  '#1565c0', '#c2185b', '#00883d', '#7928ad', '#ce3e00', '#007e94',
  '#b18a00', '#3445b4', '#b51e22', '#007b70', '#9b3d83', '#745323',
]

// The ten-band limit applies to counts, not journey identities. Additional
// journeys receive distinct hues rather than cycling the same ten colours.
export function journeyColor(index: number): string {
  if (index < JOURNEY_COLORS.length) return JOURNEY_COLORS[index]
  const hue = ((index - JOURNEY_COLORS.length) * 137.508 + 20) % 360
  return `hsl(${hue.toFixed(1)}, 80%, ${index % 2 ? 36 : 46}%)`
}
