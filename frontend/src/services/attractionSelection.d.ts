import type { AttractionCandidate, AttractionCandidatePage } from '@/types'

export interface CandidateCityInput {
  city: string
  days: number
}

export interface CandidateDiscoveryState {
  pages: Record<string, AttractionCandidatePage>
  selectedPoiIds: string[]
}

export function failedCandidatePage(city: string): AttractionCandidatePage
export function buildCandidateDiscoveryState(
  cities: CandidateCityInput[],
  results: PromiseSettledResult<AttractionCandidatePage>[],
): CandidateDiscoveryState
export function selectedCandidateNames(
  pages: AttractionCandidatePage[],
  selectedPoiIds: string[],
): string[]
export function toggleCandidateSelection(selectedPoiIds: string[], poiId: string): string[]
export function filterCandidateItems(
  page: AttractionCandidatePage | undefined,
  query: string,
): AttractionCandidate[]
export function visibleCandidateItems(
  page: AttractionCandidatePage | undefined,
  query: string,
  limit?: number,
): AttractionCandidate[]
export function findCandidatePageKey(
  pages: Record<string, AttractionCandidatePage>,
  poiId: string,
): string | undefined
export function hasCandidateImage(candidate: AttractionCandidate): boolean
