import { getRuntimeApiBaseUrl } from './api'

export interface AttractionIntroData { summary: string; source_url: string }
const pending = new Map<string, Promise<AttractionIntroData | null>>()
const queue: Array<() => void> = []
let active = 0

export function fetchAttractionIntro(name: string, city: string): Promise<AttractionIntroData | null> {
  if (!name || !city) return Promise.resolve(null)
  const params = new URLSearchParams({ name, city })
  const key = params.toString()
  const cached = pending.get(key)
  if (cached) return cached
  const request = (async () => {
    if (active >= 3) await new Promise<void>(resolve => queue.push(resolve))
    else active++
    try {
      const response = await fetch(`${getRuntimeApiBaseUrl()}/api/poi/intro?${params}`, { signal: AbortSignal.timeout(12000) })
      if (!response.ok) return null
      const { data } = await response.json()
      if (typeof data?.summary !== 'string' || !data.summary || [...data.summary].length > 30
        || typeof data.source_url !== 'string' || !data.source_url.startsWith('https://zh.wikipedia.org/wiki/')) return null
      return data as AttractionIntroData
    } catch {
      return null
    } finally {
      const next = queue.shift()
      if (next) next()
      else active--
    }
  })()
  pending.set(key, request)
  if (pending.size > 128) pending.delete(pending.keys().next().value!)
  return request
}
