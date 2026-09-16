import axios from 'axios'
import type {
  AttractionCandidate,
  AttractionCandidatePage,
  BackendRuntimeSettings,
  RuntimeSettings,
  TripFormData,
  TripHistoryItem,
  PlanDiff,
  ReviewDecision,
  TripPlanResponse,
  TripReviewRecord,
  TripTaskEvent,
  TripTaskRecord,
  TripVersionRecord,
} from '@/types'
import { i18n } from '@/i18n'

const ENV_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const ENV_AMAP_WEB_JS_KEY = import.meta.env.VITE_AMAP_WEB_JS_KEY ?? ''
const RUNTIME_API_BASE_STORAGE_KEY = 'tripstar.runtime.api_base_url'
const RUNTIME_AMAP_WEB_JS_KEY_STORAGE_KEY = 'tripstar.runtime.amap_web_js_key'
const API_ACCESS_CODE_STORAGE_KEY = 'journeyops.api_access_code'
const DEFAULT_RUNTIME_BACKEND_SETTINGS: BackendRuntimeSettings = {
  vite_amap_web_js_key: '',
  vite_amap_security_js_code: '',
  openai_base_url: '',
  openai_model: '',
  demo_mode: false,
  planner_engine: 'legacy',
  llm_configured: false,
  amap_web_configured: false,
  amap_web_js_configured: false,
  google_maps_configured: false,
  runtime_secret_updates_enabled: false,
}

export const RUNTIME_SETTINGS_UPDATED_EVENT = 'tripstar:runtime-settings-updated'
const t = i18n.global.t

const normalizeBaseUrl = (value: string | null | undefined): string => {
  const text = String(value ?? '').trim()
  return text.replace(/\/+$/, '')
}

const normalizeText = (value: unknown): string => String(value ?? '').trim()

const resolveDefaultApiBaseUrl = (): string => {
  const fromEnv = normalizeBaseUrl(ENV_API_BASE_URL)
  if (fromEnv) return fromEnv
  // 同源部署（Docker / 云端）：API 与前端在同一 origin 下
  if (typeof window !== 'undefined' && window.location) {
    return normalizeBaseUrl(window.location.origin) || ''
  }
  // 仅本地开发 fallback
  return 'http://localhost:8000'
}

const DEFAULT_API_BASE_URL = resolveDefaultApiBaseUrl()
const DEFAULT_AMAP_WEB_JS_KEY = normalizeText(ENV_AMAP_WEB_JS_KEY)

interface SubmitTripPlanResponse {
  task_id: string
  trip_id: string
  trace_id: string
  plan_id: string
  status: 'queued' | 'processing'
  ws_url: string
  message: string
}

interface GenerateTripPlanOptions {
  onTaskCreated?: (task: SubmitTripPlanResponse) => void
  onTaskEvent?: (event: TripTaskEvent) => void
}

interface RuntimeSettingsApiResponse {
  success: boolean
  message?: string
  data?: Partial<BackendRuntimeSettings>
}

interface TripHistoryResponse {
  items?: TripHistoryItem[]
}

export const getRuntimeApiBaseUrl = (): string => {
  if (typeof window === 'undefined') {
    return DEFAULT_API_BASE_URL
  }
  const saved = normalizeBaseUrl(window.localStorage.getItem(RUNTIME_API_BASE_STORAGE_KEY))
  return saved || DEFAULT_API_BASE_URL
}

export const setRuntimeApiBaseUrl = (value: string): string => {
  const normalized = normalizeBaseUrl(value) || DEFAULT_API_BASE_URL
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(RUNTIME_API_BASE_STORAGE_KEY, normalized)
  }
  return normalized
}

export const getRuntimeMapJsKey = (): string => {
  if (typeof window === 'undefined') {
    return DEFAULT_AMAP_WEB_JS_KEY
  }
  const saved = normalizeText(window.localStorage.getItem(RUNTIME_AMAP_WEB_JS_KEY_STORAGE_KEY))
  return saved || DEFAULT_AMAP_WEB_JS_KEY
}

export const setRuntimeMapJsKey = (value: string): string => {
  const normalized = normalizeText(value)
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(RUNTIME_AMAP_WEB_JS_KEY_STORAGE_KEY, normalized)
  }
  return normalized
}

const getWsBaseUrl = (): string => getRuntimeApiBaseUrl().replace(/^http/i, 'ws').replace(/\/+$/, '')

const normalizeBackendRuntimeSettings = (
  data?: Partial<BackendRuntimeSettings>
): BackendRuntimeSettings => ({
  vite_amap_web_js_key: normalizeText(
    data?.vite_amap_web_js_key ?? DEFAULT_RUNTIME_BACKEND_SETTINGS.vite_amap_web_js_key
  ),
  vite_amap_security_js_code: normalizeText(
    data?.vite_amap_security_js_code ?? DEFAULT_RUNTIME_BACKEND_SETTINGS.vite_amap_security_js_code
  ),
  openai_base_url:
    normalizeText(data?.openai_base_url ?? DEFAULT_RUNTIME_BACKEND_SETTINGS.openai_base_url) ||
    DEFAULT_RUNTIME_BACKEND_SETTINGS.openai_base_url,
  openai_model:
    normalizeText(data?.openai_model ?? DEFAULT_RUNTIME_BACKEND_SETTINGS.openai_model) ||
    DEFAULT_RUNTIME_BACKEND_SETTINGS.openai_model,
  demo_mode: Boolean(data?.demo_mode),
  planner_engine: normalizeText(data?.planner_engine) || DEFAULT_RUNTIME_BACKEND_SETTINGS.planner_engine,
  llm_configured: Boolean(data?.llm_configured),
  amap_web_configured: Boolean(data?.amap_web_configured),
  amap_web_js_configured: Boolean(data?.amap_web_js_configured),
  google_maps_configured: Boolean(data?.google_maps_configured),
  runtime_secret_updates_enabled: Boolean(data?.runtime_secret_updates_enabled),
})

const emitRuntimeSettingsUpdated = () => {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(RUNTIME_SETTINGS_UPDATED_EVENT))
}

const apiClient = axios.create({
  timeout: 0, // 无超时限制，等待后端返回结果
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    config.baseURL = getRuntimeApiBaseUrl()
    if (typeof window !== 'undefined') {
      const accessCode = window.sessionStorage.getItem(API_ACCESS_CODE_STORAGE_KEY)
      if (accessCode) config.headers.set('X-Access-Code', accessCode)
    }
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

export function setApiAccessCode(accessCode: string): void {
  if (typeof window === 'undefined') return
  const normalized = accessCode.trim()
  if (normalized) window.sessionStorage.setItem(API_ACCESS_CODE_STORAGE_KEY, normalized)
  else window.sessionStorage.removeItem(API_ACCESS_CODE_STORAGE_KEY)
}

export class TripTaskFailure extends Error {
  constructor(
    message: string,
    public readonly taskId: string,
    public readonly traceId: string,
    public readonly code: string,
  ) {
    super(message)
    this.name = 'TripTaskFailure'
  }
}

const getApiErrorMessage = (error: any, fallback: string): string => (
  error?.response?.data?.error?.message
  || error?.response?.data?.detail
  || error?.message
  || fallback
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    return Promise.reject(error)
  }
)

export async function getBackendRuntimeSettings(): Promise<BackendRuntimeSettings> {
  try {
    const response = await apiClient.get<RuntimeSettingsApiResponse>('/api/settings')
    return normalizeBackendRuntimeSettings(response.data?.data)
  } catch (error: any) {
    console.error('读取运行时配置失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '读取配置失败')
  }
}

export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  const backend = await getBackendRuntimeSettings()
  const apiBaseUrl = getRuntimeApiBaseUrl()
  const mapJsKey = getRuntimeMapJsKey() || backend.vite_amap_web_js_key

  return {
    api_base_url: apiBaseUrl,
    ...backend,
    vite_amap_web_js_key: mapJsKey,
  }
}

export async function saveRuntimeSettings(settings: RuntimeSettings): Promise<RuntimeSettings> {
  const apiBaseUrl = setRuntimeApiBaseUrl(settings.api_base_url)
  const mapJsKey = setRuntimeMapJsKey(settings.vite_amap_web_js_key)

  emitRuntimeSettingsUpdated()

  return {
    ...settings,
    api_base_url: apiBaseUrl,
    vite_amap_web_js_key: mapJsKey,
  }
}

/**
 * 提交旅行规划任务（立即返回 task_id）
 */
export async function submitTripPlan(formData: TripFormData): Promise<SubmitTripPlanResponse> {
  try {
    const response = await apiClient.post<TripTaskRecord>('/api/v2/trips', {
      origin: formData.origin,
      destinations: formData.cities?.length
        ? formData.cities
        : [{ city: formData.city, days: formData.travel_days }],
      start_date: formData.start_date,
      end_date: formData.end_date,
      travel_days: formData.travel_days,
      budget_total: formData.budget_total,
      currency: formData.currency || 'CNY',
      travelers: formData.travelers || 1,
      transport_preferences: formData.transportation ? [formData.transportation] : [],
      accommodation_preference: formData.accommodation || null,
      interests: formData.preferences,
      must_visit: formData.must_visit || [],
      avoid: formData.avoid || [],
      pace: formData.pace || 'balanced',
      daily_start_time: formData.daily_start_time || '09:00:00',
      daily_end_time: formData.daily_end_time || '21:00:00',
      max_daily_walking_minutes: formData.max_daily_walking_minutes,
      accessibility_needs: formData.accessibility_needs || [],
      free_text_input: formData.free_text_input,
      language: formData.language || 'zh',
      timezone: 'Asia/Shanghai',
    })
    const task = response.data
    return {
      task_id: task.task_id,
      trip_id: task.trip_id,
      trace_id: task.trace_id,
      plan_id: task.task_id,
      status: task.status === 'processing' ? 'processing' : 'queued',
      ws_url: `/api/v2/trips/tasks/${task.task_id}/ws`,
      message: task.message,
    }
  } catch (error: any) {
    console.error('提交旅行计划失败:', error)
    throw new Error(getApiErrorMessage(error, t('api.submitTripPlanFailed')))
  }
}

export async function getAttractionCandidates(
  city: string,
  days: number,
  interests: string[] = []
): Promise<AttractionCandidatePage> {
  try {
    const response = await apiClient.get<AttractionCandidatePage>('/api/v2/attractions/candidates', {
      params: { city, days, limit: 40, interests },
      paramsSerializer: { indexes: null },
      timeout: 30000,
    })
    return response.data
  } catch (error: any) {
    throw new Error(getApiErrorMessage(error, t('api.attractionCandidatesFailed')))
  }
}

export async function resolveAttractionImage(candidate: AttractionCandidate): Promise<AttractionCandidate> {
  if (candidate.image.url) return candidate
  try {
    const response = await apiClient.get('/api/poi/photo', {
      params: { name: candidate.name, city: candidate.city, poi_id: candidate.poi_id },
      timeout: 20000,
    })
    const data = response.data?.data
    if (!data) return candidate
    return {
      ...candidate,
      image: {
        url: data.image_url || data.photo_url || '',
        source: data.source || 'placeholder',
        author: data.author || '',
        license: data.license || '',
        source_page: data.source_page || '',
        attribution: data.attribution || '',
      },
    }
  } catch {
    return candidate
  }
}

/**
 * 轮询任务状态
 */
export async function pollTaskStatus(taskId: string): Promise<any> {
  try {
    const response = await apiClient.get(`/api/trip/status/${taskId}`)
    return response.data
  } catch (error: any) {
    console.error('查询任务状态失败:', error)
    throw new Error(error.response?.data?.detail || error.message || t('api.queryTaskStatusFailed'))
  }
}

export async function getTripHistory(limit = 8): Promise<TripHistoryItem[]> {
  try {
    const response = await apiClient.get<TripHistoryResponse>('/api/trip/history', {
      params: { limit },
    })
    return Array.isArray(response.data?.items) ? response.data.items : []
  } catch (error: any) {
    console.error('查询历史计划失败:', error)
    throw new Error(error.response?.data?.detail || error.message || t('api.queryTaskStatusFailed'))
  }
}

const watchTripPlanTask = (
  task: SubmitTripPlanResponse,
  options?: GenerateTripPlanOptions,
): Promise<TripPlanResponse> => {
  const wsUrl = task.ws_url.startsWith('ws://') || task.ws_url.startsWith('wss://')
    ? task.ws_url
    : `${getWsBaseUrl()}${task.ws_url}`

  return new Promise((resolve, reject) => {
    let settled = false
    const socket = new WebSocket(wsUrl)

    const safeResolve = (value: TripPlanResponse) => {
      if (settled) return
      settled = true
      socket.close()
      resolve(value)
    }

    const safeReject = (error: unknown) => {
      if (settled) return
      settled = true
      socket.close()
      reject(error)
    }

    socket.onmessage = (ev) => {
      try {
        const rawEvent = JSON.parse(ev.data) as Omit<TripTaskEvent, 'plan_id'> & { plan_id?: string }
        const event: TripTaskEvent = {
          ...rawEvent,
          plan_id: rawEvent.plan_id || rawEvent.task_id,
        }
        options?.onTaskEvent?.(event)

        if (event.status === 'completed') {
          if (!event.result) {
            safeReject(new Error(t('api.generateTripPlanFailed')))
            return
          }
          safeResolve({
            ...event.result,
            task_id: event.task_id,
            trip_id: event.trip_id || event.review?.trip_id,
            review: event.review,
          })
          return
        }

        if (event.status === 'awaiting_approval') {
          if (!event.result) {
            safeReject(new Error(t('api.generateTripPlanFailed')))
            return
          }
          safeResolve({
            ...event.result,
            task_id: event.task_id,
            trip_id: event.trip_id || event.review?.trip_id,
            review: event.review,
          })
          return
        }

        if (['failed', 'cancelled', 'rejected'].includes(event.status)) {
          const error = typeof event.error === 'string' ? { code: event.status, message: event.error } : event.error
          safeReject(new TripTaskFailure(
            error?.message || event.message || t('api.generateTripPlanFailed'),
            event.task_id,
            event.trace_id || task.trace_id,
            error?.code || event.status,
          ))
        }
      } catch (err) {
        safeReject(err)
      }
    }

    socket.onerror = () => {
      safeReject(new TripTaskFailure(
        t('api.generateTripPlanFailed'),
        task.task_id,
        task.trace_id,
        'websocket_error',
      ))
    }

    socket.onclose = () => {
      if (!settled) {
        safeReject(new TripTaskFailure(
          t('api.generateTripPlanFailed'),
          task.task_id,
          task.trace_id,
          'websocket_closed',
        ))
      }
    }
  })
}

export async function generateTripPlan(
  formData: TripFormData,
  options?: GenerateTripPlanOptions
): Promise<TripPlanResponse> {
  const task = await submitTripPlan(formData)
  options?.onTaskCreated?.(task)
  return watchTripPlanTask(task, options)
}

export async function retryTripPlan(
  taskId: string,
  options?: GenerateTripPlanOptions,
): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripTaskRecord>(`/api/v2/trips/tasks/${taskId}/retry`)
    const record = response.data
    const task: SubmitTripPlanResponse = {
      task_id: record.task_id,
      trip_id: record.trip_id,
      trace_id: record.trace_id,
      plan_id: record.task_id,
      status: record.status === 'processing' ? 'processing' : 'queued',
      ws_url: `/api/v2/trips/tasks/${record.task_id}/ws`,
      message: record.message,
    }
    options?.onTaskCreated?.(task)
    return watchTripPlanTask(task, options)
  } catch (error: any) {
    if (error instanceof TripTaskFailure) throw error
    throw new Error(getApiErrorMessage(error, t('api.generateTripPlanFailed')))
  }
}

export async function getTripTask(taskId: string): Promise<TripTaskRecord> {
  const response = await apiClient.get<TripTaskRecord>(`/api/v2/trips/tasks/${taskId}`)
  return response.data
}

export async function submitTripReview(
  taskId: string,
  decision: ReviewDecision
): Promise<TripTaskRecord> {
  const response = await apiClient.post<TripTaskRecord>(
    `/api/v2/trips/tasks/${taskId}/review`,
    decision
  )
  return response.data
}

export async function waitForTripTask(
  taskId: string,
  options: { timeoutMs?: number; intervalMs?: number } = {}
): Promise<TripTaskRecord> {
  const timeoutMs = options.timeoutMs ?? 10 * 60 * 1000
  const intervalMs = options.intervalMs ?? 1500
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const task = await getTripTask(taskId)
    if (['awaiting_approval', 'completed', 'rejected', 'failed', 'cancelled'].includes(task.status)) {
      return task
    }
    await new Promise(resolve => window.setTimeout(resolve, intervalMs))
  }
  throw new Error('Timed out while waiting for the trip workflow.')
}

export async function getTripReviews(tripId: string): Promise<TripReviewRecord[]> {
  const response = await apiClient.get<TripReviewRecord[]>(`/api/v2/trips/${tripId}/reviews`)
  return response.data
}

export async function getTripVersions(tripId: string): Promise<TripVersionRecord[]> {
  const response = await apiClient.get<TripVersionRecord[]>(`/api/v2/trips/${tripId}/versions`)
  return response.data
}

export async function getTripVersion(
  tripId: string,
  version: number
): Promise<TripVersionRecord> {
  const response = await apiClient.get<TripVersionRecord>(
    `/api/v2/trips/${tripId}/versions/${version}`
  )
  return response.data
}

export async function compareTripVersions(
  tripId: string,
  fromVersion: number,
  toVersion: number
): Promise<PlanDiff> {
  const response = await apiClient.get<PlanDiff>(
    `/api/v2/trips/${tripId}/versions/${fromVersion}/compare/${toVersion}`
  )
  return response.data
}

export async function rollbackTripVersion(
  tripId: string,
  version: number,
  reason: string
): Promise<TripVersionRecord> {
  const response = await apiClient.post<TripVersionRecord>(
    `/api/v2/trips/${tripId}/versions/${version}/rollback`,
    { reason }
  )
  return response.data
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || t('api.healthCheckFailed'))
  }
}

export default apiClient

