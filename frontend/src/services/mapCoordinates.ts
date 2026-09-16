export type RoutePoint = [number, number]

export function toRoutePoint(raw: any): RoutePoint | null {
  if (!raw || typeof raw !== 'object') return null
  const pair = Array.isArray(raw) ? raw
    : typeof raw.getLng === 'function' && typeof raw.getLat === 'function'
      ? [raw.getLng(), raw.getLat()]
      : 'lng' in raw ? [raw.lng, raw.lat] : [raw.longitude, raw.latitude]
  if (pair.length < 2 || pair.slice(0, 2).some(value =>
    (typeof value !== 'number' && typeof value !== 'string') || String(value).trim() === '')) return null
  const lng = Number(pair[0])
  const lat = Number(pair[1])
  return Number.isFinite(lng) && Number.isFinite(lat)
    && Math.abs(lng) <= 180 && Math.abs(lat) <= 90 && !(lng === 0 && lat === 0)
    ? [lng, lat] : null
}
