// Enrich existing transfer rows without changing saved times or itinerary versions.
export function transferDetails(item: { title: string }, summary?: Record<string, any> | null) {
  if (!summary) return null
  const outbound = summary.outbound
  const inbound = summary.return
  const hotel = summary.hotel
  if (item.title.startsWith('出发城市内接驳') && outbound?.origin_location) {
    return { title: `前往${outbound.origin_location.name}（预估60分钟，请按实际出发位置核实）`, place: outbound.origin_location, from: undefined, city: summary.planning_request?.origin }
  }
  if (item.title.startsWith('到站后接驳至酒店') && outbound?.location && hotel) {
    return { title: `${outbound.location.name} → ${hotel.name}（接驳估算）`, place: hotel, from: outbound.location, city: undefined }
  }
  if (item.title.startsWith('酒店至返程枢纽') && inbound?.location && hotel) {
    return { title: `${hotel.name} → ${inbound.location.name}（接驳估算）`, place: inbound.location, from: hotel, city: undefined }
  }
  return null
}
