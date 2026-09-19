import type { DayPlan, RouteEstimate, ScheduleItem } from '@/types'

export function drivingTransfers(item: ScheduleItem, day: DayPlan, routes: RouteEstimate[] = [], summary?: Record<string, any> | null) {
  const route = routes.find(route => route.estimate_id === item.route_estimate_id
    && route.provider === 'amap-driving' && route.mode === 'driving' && route.status !== 'unavailable')
  if (!route || item.item_type !== 'transport') return []
  const places = [...day.attractions, ...day.meals, day.hotel, summary?.hotel, summary?.outbound?.location, summary?.return?.location].filter(Boolean)
  const from = places.find(place => place.name === route.origin)
  const place = places.find(place => place.name === route.destination)
  return from && place ? [{ from, place, detail: route.detail }] : []
}

// Enrich existing transfer rows without changing saved times or itinerary versions.
export function transferDetails(item: { title: string }, summary?: Record<string, any> | null) {
  if (!summary) return null
  const outbound = summary.outbound
  const inbound = summary.return
  const hotel = summary.hotel
  const label = item.title.includes('驾车') ? '驾车，费用未评估' : '接驳估算'
  if (item.title.startsWith('出发城市内接驳') && outbound?.origin_location) {
    return { title: `前往${outbound.origin_location.name}（预估60分钟，请按实际出发位置核实）`, place: outbound.origin_location, from: undefined, city: summary.planning_request?.origin }
  }
  if (item.title.startsWith('到站后接驳至酒店') && outbound?.location && hotel) {
    return { title: `${outbound.location.name} → ${hotel.name}（${label}）`, place: hotel, from: outbound.location, city: undefined }
  }
  if (item.title.startsWith('酒店至返程枢纽') && inbound?.location && hotel) {
    return { title: `${hotel.name} → ${inbound.location.name}（${label}）`, place: inbound.location, from: hotel, city: undefined }
  }
  return null
}
