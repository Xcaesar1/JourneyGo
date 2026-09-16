import type { DayPlan, Location } from '@/types'

export interface NavigationPlace {
  name: string
  address?: string
  location?: Location | null
  poi_id?: string
}
export interface NavigationStop extends NavigationPlace {
  id: string
  time?: string
}
export type TravelMode = 'walk' | 'bus'
export type StopStatus = 'done' | 'skipped'

export function canRoute(place: NavigationPlace): boolean {
  const loc = place.location
  // Old plans mix map providers without a coordinate-system field. Only use
  // coordinates attached to an AMap POI; unknown locations go through search.
  return /^B[A-Z0-9]+$/i.test(place.poi_id || '') && !!loc
    && Number.isFinite(loc.longitude) && Number.isFinite(loc.latitude)
    && loc.longitude >= -180 && loc.longitude <= 180
    && loc.latitude >= -90 && loc.latitude <= 90
    && !(loc.longitude === 0 && loc.latitude === 0)
}

export function amapUrl(place: NavigationPlace, city: string, mode: TravelMode,
  native = true, from?: NavigationPlace): string {
  const params = new URLSearchParams({ src: 'JourneyOps', callnative: native ? '1' : '0' })
  const point = (value: NavigationPlace) =>
    `${value.location!.longitude},${value.location!.latitude},${value.name.replace(/,/g, ' ')}`
  if (canRoute(place) && (!from || canRoute(from))) {
    params.set('to', point(place))
    if (from) params.set('from', point(from))
    params.set('mode', mode)
    params.set('coordinate', 'gaode')
    params.set('policy', '0')
    return `https://uri.amap.com/navigation?${params}`
  }
  params.set('keyword', [place.name, place.address].filter(Boolean).join(' '))
  params.set('city', city)
  return `https://uri.amap.com/search?${params}`
}

export function dayStops(day: DayPlan): NavigationStop[] {
  const places = [
    ...day.attractions.map(place => ({ place, type: 'attraction' })),
    ...day.meals.map(place => ({ place, type: 'meal' })),
  ]
  const remaining = new Set(places)
  const stops: NavigationStop[] = []
  for (const item of day.timeline || []) {
    if (item.item_type !== 'attraction' && item.item_type !== 'meal') continue
    const match = places.find(entry => remaining.has(entry) && entry.type === item.item_type
      && entry.place.name === (item.reference_name || item.title))
    if (!match) continue
    remaining.delete(match)
    stops.push({ ...match.place, id: `timeline:${item.item_id}`, time: item.start.slice(11, 16) })
  }
  for (const entry of remaining) {
    stops.push({ ...entry.place, id: `place:${entry.type}:${places.indexOf(entry)}` })
  }
  if (day.hotel) stops.push({ ...day.hotel, id: 'hotel' })
  return stops
}

export function progressKey(planId: string, day: DayPlan): string {
  // Include the exact itinerary so changed routes never inherit stale progress.
  return `journeyops:progress:v1:${JSON.stringify([planId, day.date, day.day_index,
    dayStops(day).map(s => [s.id, s.name, s.address, s.poi_id, s.location, s.time])])}`
}

export function parseProgress(raw: string | null, stops: NavigationStop[]): Record<string, StopStatus> {
  try {
    const data: unknown = JSON.parse(raw || '{}')
    if (!data || typeof data !== 'object' || Array.isArray(data)) return {}
    return Object.fromEntries(stops.flatMap(stop => {
      const status = (data as Record<string, unknown>)[stop.id]
      return status === 'done' || status === 'skipped' ? [[stop.id, status]] : []
    }))
  } catch { return {} }
}
