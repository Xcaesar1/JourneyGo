export const failedCandidatePage = city => ({
  city,
  items: [],
  total: 0,
  default_selected_ids: [],
  degraded: true,
  issues: ['request_failed'],
})

export const buildCandidateDiscoveryState = (cities, results) => {
  const pages = {}
  const availableIds = new Set()
  const requestedDefaults = []

  cities.forEach((item, index) => {
    const city = item.city.trim()
    const result = results[index]
    const page = result?.status === 'fulfilled' ? result.value : failedCandidatePage(city)
    pages[city] = page
    page.items.forEach(candidate => availableIds.add(candidate.poi_id))
    requestedDefaults.push(...page.default_selected_ids)
  })

  return {
    pages,
    selectedPoiIds: Array.from(new Set(requestedDefaults.filter(id => availableIds.has(id)))),
  }
}

export const selectedCandidateNames = (pages, selectedPoiIds) => {
  const selected = new Set(selectedPoiIds)
  return pages.flatMap(page => page.items)
    .filter(candidate => selected.has(candidate.poi_id))
    .map(candidate => candidate.name)
}

export const toggleCandidateSelection = (selectedPoiIds, poiId) => (
  selectedPoiIds.includes(poiId)
    ? selectedPoiIds.filter(id => id !== poiId)
    : [...selectedPoiIds, poiId]
)

export const filterCandidateItems = (page, query) => {
  if (!page) return []
  const normalized = query.trim().toLocaleLowerCase()
  if (!normalized) return page.items
  return page.items.filter(candidate => (
    `${candidate.name} ${candidate.category} ${candidate.address}`
      .toLocaleLowerCase()
      .includes(normalized)
  ))
}

export const visibleCandidateItems = (page, query, limit = 8) => (
  filterCandidateItems(page, query).slice(0, limit)
)

export const findCandidatePageKey = (pages, poiId) => Object.entries(pages)
  .find(([, page]) => page.items.some(candidate => candidate.poi_id === poiId))?.[0]

export const hasCandidateImage = candidate => Boolean(candidate.image.url)
