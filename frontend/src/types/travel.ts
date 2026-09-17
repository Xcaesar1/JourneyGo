export type TravelProvider = 'train' | 'hotel' | 'flight'

export interface TravelSearchRequest {
  provider: TravelProvider
  origin: string
  destination: string
  date: string
  country: string
  nights: number
  adults: number
  high_speed_only: boolean
  confirm_paid: boolean
}

export interface TravelOffer {
  offer_id: string
  title: string
  subtitle: string
  departure: string
  arrival: string
  price: number | null
  currency: string
  price_basis: 'per_person' | 'stay_total' | 'first_night_reference'
  estimated_stay_total?: number | null
  fare_label: string
  availability: string
  booking_url: string
  notes: string[]
}

export interface TravelSearchResponse {
  provider: TravelProvider
  status: 'ok' | 'empty' | 'disabled' | 'unavailable' | 'busy' | 'budget_exhausted'
  message: string
  offers: TravelOffer[]
  source_title: string
  source_url: string
  source_domain: string
  trust_level: string
  fetched_at: string | null
  cached: boolean
  query: TravelSearchRequest
}

export type TravelCapabilities = Record<TravelProvider, { enabled: boolean; paid: boolean }>
