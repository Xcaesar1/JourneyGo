import type { Dayjs } from 'dayjs'
import type { AttractionCandidatePage, TripHistoryItem } from '@/types'

export type LandingFormData = {
  origin: string
  cities: Array<{ city: string; days: number }>
  start_date: Dayjs | null
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input: string
  budget_total: number
  travelers: number
  pace: 'relaxed' | 'balanced' | 'intensive'
  daily_start_time: Dayjs
  daily_end_time: Dayjs
  max_daily_walking_minutes: number
}

// Navigation-only state: never persist trip drafts or history to browser storage.
export const memoriesState = {
  landing: null as null | {
    form: LandingFormData
    candidatePages: Record<string, AttractionCandidatePage>
    selectedPoiIds: string[]
    candidateSearch: Record<string, string>
    candidateVisible: Record<string, number>
    discoverySignature: string
    scrollY: number
  },
  items: null as TripHistoryItem[] | null,
  scrollY: 0,
}
