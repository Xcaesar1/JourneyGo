// 类型定义

export interface CityStay {
  city: string
  days: number
}

export interface Location {
  longitude: number
  latitude: number
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  poi_id?: string
  image_source?: string
  image_author?: string
  image_license?: string
  image_source_page?: string
  image_attribution?: string
  recommendation_reason?: string
  ticket_price?: number
  opening_time?: string | null
  closing_time?: string | null
  closed_dates?: string[]
  source_evidence_ids?: string[]
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  name: string
  address?: string
  location?: Location
  description?: string
  estimated_cost?: number
}

export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total_inter_city_transport?: number
  total: number
}

export interface DayPlan {
  date: string
  day_index: number
  city?: string
  is_transfer_day?: boolean
  transfer_info?: string
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
  timeline?: ScheduleItem[]
  arrangement_rationale?: string
}

export type ScheduleItemType = 'attraction' | 'meal' | 'transport' | 'free_time'

export interface ScheduleItem {
  item_id: string
  item_type: ScheduleItemType
  title: string
  start: string
  end: string
  duration_minutes: number
  location?: Location | null
  reference_name?: string | null
  route_estimate_id?: string | null
  estimated_cost: number
  opening_time?: string | null
  closing_time?: string | null
  closed_dates?: string[]
  source_evidence_ids?: string[]
}

export type RouteEstimateStatus = 'verified' | 'estimated' | 'unavailable'

export interface RouteEstimate {
  estimate_id: string
  origin: string
  destination: string
  mode: 'driving' | 'walking' | 'straight_line'
  distance_meters?: number | null
  duration_minutes?: number | null
  provider: string
  status: RouteEstimateStatus
  detail: string
}

export type IntercityTransportMode = 'train' | 'flight' | 'coach' | 'driving' | 'public_transit'

export interface IntercityTransportOption {
  option_id: string
  leg_index: number
  origin: string
  destination: string
  mode: IntercityTransportMode
  recommended: boolean
  estimated_duration_minutes?: number | null
  estimated_cost_per_person?: number | null
  currency: string
  route_estimate_id?: string | null
  estimate_status: RouteEstimateStatus
  advice: string
  caveats: string[]
}

export type ValidationSeverity = 'critical' | 'warning' | 'info'

export interface ValidationIssue {
  code: string
  severity: ValidationSeverity
  day_index?: number | null
  item_id?: string | null
  message: string
  evidence_ids: string[]
  suggested_action?: string | null
}

export interface ValidationReport {
  issues: ValidationIssue[]
}

export interface WeatherInfo {
  date: string
  city?: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export type SourceClaimType = 'opening_hours' | 'closure' | 'reservation' | 'events' | 'travel_tips'
export type SourceTrustLevel = 'official' | 'major_platform' | 'community' | 'unknown'
export type SourceFreshnessStatus = 'fresh' | 'stale' | 'unknown'

export interface SourceEvidence {
  id: string
  title: string
  url?: string | null
  domain: string
  provider: string
  claim_type: SourceClaimType
  claim_text: string
  published_at?: string | null
  fetched_at: string
  freshness_status: SourceFreshnessStatus
  trust_level: SourceTrustLevel
  confidence: number
}

export interface TripPlan {
  origin?: string
  city: string
  cities?: string[]
  start_date: string
  end_date: string
  days: DayPlan[]
  transport_options?: IntercityTransportOption[]
  route_matrix?: RouteEstimate[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
  source_evidence?: SourceEvidence[]
  research_updated_at?: string | null
  research_status?: 'complete' | 'partial' | 'unavailable'
  validation_report?: ValidationReport
  revision_count?: number
}

export interface TripFormData {
  origin: string
  city: string
  cities?: CityStay[]
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  must_visit?: string[]
  avoid?: string[]
  free_text_input: string
  language?: string
  budget_total?: number
  currency?: string
  travelers?: number
  pace?: 'relaxed' | 'balanced' | 'intensive'
  daily_start_time?: string
  daily_end_time?: string
  max_daily_walking_minutes?: number
  accessibility_needs?: string[]
}

export interface AttractionImageMetadata {
  url: string
  source: 'amap' | 'openverse' | 'placeholder' | string
  author: string
  license: string
  source_page: string
  attribution: string
}

export interface AttractionCandidate {
  poi_id: string
  name: string
  city: string
  address: string
  longitude: number | null
  latitude: number | null
  category: string
  rating: number | null
  image: AttractionImageMetadata
  recommendation_score: number
  recommendation_reason: string
  matched_interests: string[]
  is_must_visit: boolean
}

export interface AttractionCandidatePage {
  city: string
  items: AttractionCandidate[]
  total: number
  default_selected_ids: string[]
  degraded: boolean
  issues: string[]
}

export interface TripPlanResponse {
  success: boolean
  message: string
  plan_id?: string
  task_id?: string
  trip_id?: string
  review?: TripReviewRecord
  data?: TripPlan
  graph_data?: KnowledgeGraphData
}

export interface TripHistoryItem {
  plan_id: string
  task_id: string
  city: string
  start_date: string
  end_date: string
  travel_days: number
  updated_at: string
  overall_suggestions?: string
}

export type TripTaskStatus =
  | 'queued'
  | 'processing'
  | 'retrying'
  | 'awaiting_approval'
  | 'cancel_requested'
  | 'cancelled'
  | 'completed'
  | 'rejected'
  | 'failed'

export type TripTaskStage =
  | 'submitted'
  | 'initializing'
  | 'attraction_search'
  | 'weather_search'
  | 'hotel_search'
  | 'planning'
  | 'workflow_start'
  | 'normalize_request'
  | 'prepare_research'
  | 'research_web'
  | 'collect'
  | 'transport'
  | 'draft'
  | 'enrich_plan'
  | 'validate'
  | 'revise'
  | 'human_review'
  | 'persist'
  | 'reject_plan'
  | 'replanning'
  | 'review_resume'
  | 'awaiting_approval'
  | 'graph_building'
  | 'completed'
  | 'rejected'
  | 'failed'

export interface TripTaskEvent {
  task_id: string
  plan_id: string
  trip_id?: string
  trace_id?: string
  status: TripTaskStatus
  stage: TripTaskStage
  progress: number
  message: string
  error?: string | { code: string; message: string } | null
  result?: TripPlanResponse
  review?: TripReviewRecord
}

export type ReviewAction = 'approve' | 'modify' | 'reject'
export type ReviewStatus =
  | 'requested'
  | 'pending'
  | 'changes_requested'
  | 'approved'
  | 'rejected'
  | 'superseded'
  | 'applied'

export interface ReplanRequest {
  instruction: string
  day_indices: number[]
  transport_preferences?: string[]
  budget_total?: number
  pace?: 'relaxed' | 'balanced' | 'intensive'
  add_attractions: string[]
  remove_attractions: string[]
  refresh_sources: boolean
}

export interface ReviewDecision {
  action: ReviewAction
  reason?: string
  changes?: ReplanRequest
}

export interface ImpactScope {
  day_indices: number[]
  fields: string[]
  refresh_research: boolean
  refresh_routing: boolean
  rebuild_timeline: boolean
  recalculate_budget: boolean
}

export interface PlanDiffEntry {
  path: string
  operation: 'add' | 'remove' | 'replace'
  before?: unknown
  after?: unknown
}

export interface PlanDiff {
  from_version?: number | null
  to_version?: number | null
  summary: string
  changed_day_indices: number[]
  unchanged_day_indices: number[]
  entries: PlanDiffEntry[]
}

export interface TripReviewRecord {
  review_id: string
  trip_id: string
  task_id: string
  workflow_type: 'initial' | 'replan' | 'rollback'
  status: ReviewStatus
  base_version?: number | null
  proposed_version?: number | null
  parent_review_id?: string | null
  reason: string
  change_request?: ReplanRequest | null
  impact_scope?: ImpactScope | null
  refreshed_sources: string[]
  validation_report: ValidationReport
  diff: PlanDiff
  preview?: TripPlanResponse | null
  created_at: string
  updated_at: string
  resolved_at?: string | null
}

export interface TripTaskRecord {
  task_id: string
  trip_id: string
  trace_id: string
  status: TripTaskStatus
  stage: string
  progress: number
  attempt_count: number
  max_attempts: number
  created_at: string
  updated_at: string
  started_at?: string | null
  finished_at?: string | null
  message: string
  result?: TripPlanResponse | null
  review?: TripReviewRecord | null
  error?: { code: string; message: string } | null
}

export interface TripVersionRecord {
  trip_id: string
  version: number
  active: boolean
  parent_version?: number | null
  planner_engine: string
  version_role: string
  schema_version: string
  review_id?: string | null
  change_reason: string
  change_sources: string[]
  validation_report: ValidationReport
  created_at: string
  payload?: TripPlanResponse | null
  native_payload?: unknown
}

export interface BackendRuntimeSettings {
  vite_amap_web_js_key: string
  vite_amap_security_js_code: string
  openai_base_url: string
  openai_model: string
  demo_mode: boolean
  planner_engine: string
  llm_configured: boolean
  amap_web_configured: boolean
  amap_web_js_configured: boolean
  google_maps_configured: boolean
  runtime_secret_updates_enabled: boolean
}

export interface RuntimeSettings {
  api_base_url: string
  vite_amap_web_js_key: string
  vite_amap_security_js_code: string
  openai_base_url: string
  openai_model: string
  demo_mode: boolean
  planner_engine: string
  llm_configured: boolean
  amap_web_configured: boolean
  amap_web_js_configured: boolean
  google_maps_configured: boolean
  runtime_secret_updates_enabled: boolean
}

// ============ 知识图谱类型 ============

export interface GraphNode {
  id: string
  name: string
  category: number
  symbolSize: number
  itemStyle?: { color: string }
  value?: string
}

export interface GraphEdge {
  source: string
  target: string
  label?: string
}

export interface GraphCategory {
  name: string
}

export interface KnowledgeGraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  categories: GraphCategory[]
}

// ============ AI 行程问答类型 ============

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface TripChatRequest {
  message: string
  trip_plan: object
  history: ChatMessage[]
}

export interface TripChatResponse {
  success: boolean
  reply: string
}
