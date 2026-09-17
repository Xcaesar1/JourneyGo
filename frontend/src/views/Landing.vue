<template>
  <div class="landing-page">
    <div class="lower-shade" :style="lowerShadeStyle"></div>
    <NavBar limited-languages :show-settings="false" :show-cta="false" show-memories :memories-disabled="loading || discoveryLoading"
      @memories-click="openMemories" @brand-click="scrollToTop" @cta-click="scrollToForm" />

    <div class="wrapper">
      <section class="journey-hero" aria-labelledby="hero-title">
        <div class="journey-landscape" :style="{ backgroundImage: `url(${heroImage})` }" aria-hidden="true"></div>
        <div class="journey-mist" aria-hidden="true"></div>
        <div class="journey-sunlight" aria-hidden="true"></div>
        <div class="journey-hero-shade" aria-hidden="true"></div>
        <div class="journey-hero-content">
          <h1 id="hero-title">{{ t('home.hero.title') }}</h1>
          <p class="journey-hero-copy">{{ t('home.hero.line1') }}<br />{{ t('home.hero.line2') }}</p>
          <button type="button" class="journey-explore" :disabled="loading" @click="scrollToForm">{{ t('home.hero.explore') }} <span aria-hidden="true">↗</span></button>
        </div>
      </section>
    </div>

    <section ref="formRef" class="form-section">
      <div class="form-panel" :style="[formRevealStyle, { minHeight: panelHeight === 'auto' ? 'auto' : panelHeight + 'px' }]" ref="panelRef">
        <a-form v-show="!loading" :model="formData" layout="vertical" @finish="handleSubmit">
          <section v-if="pausedTask" class="step" role="status">
            <h3>{{ t('oneClick.paused') }}</h3><p>{{ pausedTask.message }}</p>
            <p>{{ t('oneClick.retained') }}: {{ retainedQueries.length }}</p>
            <ul><li v-for="(query, index) in retainedQueries" :key="index">{{ query.provider }} · {{ query.scope }} · {{ query.status }} · {{ query.fetched_at || query.created_at }}<p v-for="line in queryPreview(query)" :key="line">{{ line }}</p></li></ul>
            <label v-if="['train', 'flight', 'hotel', 'amap'].includes(pausedTask.provider || '')"><input v-model="refreshQuote" type="checkbox" /> {{ t('oneClick.refresh') }}</label>
          </section>
          <div class="step">
            <div class="step-head">
              <span>01</span>
              <h3>{{ t('home.step1') }}</h3>
            </div>

            <a-form-item name="origin" :rules="formRules.origin">
              <template #label>
                <span class="field-label">{{ t('home.originLabel') }}</span>
              </template>
              <a-input
                v-model:value="formData.origin"
                :placeholder="t('home.originPlaceholder')"
                size="large"
                class="field-input"
              />
            </a-form-item>

            <!-- 多城市动态列表 -->
            <div class="city-list">
              <div v-for="(cs, idx) in formData.cities" :key="idx" class="city-row">
                <a-form-item class="city-row-name" :rules="[{ required: true, message: t('home.cityRequired') }]">
                  <template #label>
                    <span class="field-label">{{ t('home.cityNLabel', { n: idx + 1 }) }}</span>
                  </template>
                  <a-input
                    v-model:value="cs.city"
                    :placeholder="t('home.cityPlaceholder')"
                    size="large"
                    class="field-input"
                  />
                </a-form-item>
                <a-form-item class="city-row-days">
                  <template #label>
                    <span class="field-label">{{ t('home.cityStayDays') }}</span>
                  </template>
                  <a-input-number
                    v-model:value="cs.days"
                    :min="oneClickEnabled ? 2 : 1"
                    :max="15"
                    size="large"
                    class="field-input"
                    style="width: 100%"
                  />
                </a-form-item>
                <button
                  v-if="!oneClickEnabled && formData.cities.length > 1"
                  type="button"
                  class="city-remove-btn"
                  @click="removeCity(idx)"
                >×</button>
              </div>
              <button v-if="!oneClickEnabled" type="button" class="city-add-btn" @click="addCity">
                + {{ t('home.addCity') }}
              </button>
            </div>

            <!-- 日期与天数 -->
            <div class="grid grid-date">
              <a-form-item name="start_date" :rules="formRules.startDate">
                <template #label>
                  <span class="field-label">{{ t('home.startDateLabel') }}</span>
                </template>
                <a-date-picker
                  v-model:value="formData.start_date"
                  style="width: 100%"
                  size="large"
                  class="field-input"
                  :placeholder="t('home.startDatePlaceholder')"
                />
              </a-form-item>

              <a-form-item>
                <template #label>
                  <span class="field-label">{{ t('home.travelDaysLabel') }}</span>
                </template>
                <div class="days-chip">
                  <span class="days-number">{{ totalDays }}</span>
                  <span class="days-unit">{{ t('home.travelDaysUnit') }}</span>
                </div>
              </a-form-item>
            </div>
          </div>

          <div class="step">
            <div class="step-head">
              <span>02</span>
              <h3>{{ t('home.step2') }}</h3>
            </div>
            <div class="grid grid2">
              <a-form-item name="transportation">
                <template #label>
                  <span class="field-label">{{ t('home.transportationLabel') }}</span>
                </template>
                <a-select v-model:value="formData.transportation" size="large" class="field-select">
                  <template v-if="oneClickEnabled">
                    <a-select-option value="train">{{ t('oneClick.train') }}</a-select-option>
                    <a-select-option value="flight">{{ t('oneClick.flight') }}</a-select-option>
                  </template>
                  <template v-else>
                  <a-select-option value="公共交通">{{ t('home.transportation.public') }}</a-select-option>
                  <a-select-option value="自驾">{{ t('home.transportation.drive') }}</a-select-option>
                  <a-select-option value="步行">{{ t('home.transportation.walk') }}</a-select-option>
                  <a-select-option value="混合">{{ t('home.transportation.mixed') }}</a-select-option>
                  </template>
                </a-select>
              </a-form-item>

              <a-form-item name="accommodation">
                <template #label>
                  <span class="field-label">{{ t('home.accommodationLabel') }}</span>
                </template>
                <a-select v-model:value="formData.accommodation" size="large" class="field-select">
                  <template v-if="oneClickEnabled">
                    <a-select-option v-for="tier in ['economy', 'business', 'premium']" :key="tier" :value="tier">{{ t('oneClick.' + tier) }}</a-select-option>
                  </template>
                  <template v-else>
                  <a-select-option value="经济型酒店">{{ t('home.accommodation.budget') }}</a-select-option>
                  <a-select-option value="舒适型酒店">{{ t('home.accommodation.comfort') }}</a-select-option>
                  <a-select-option value="豪华酒店">{{ t('home.accommodation.luxury') }}</a-select-option>
                  <a-select-option value="民宿">{{ t('home.accommodation.homestay') }}</a-select-option>
                  </template>
                </a-select>
              </a-form-item>
            </div>

            <div class="grid grid4 constraint-grid">
              <a-form-item name="budget_total">
                <template #label><span class="field-label">{{ t('home.budgetLabel') }}</span></template>
                <a-input-number v-model:value="formData.budget_total" :min="100" :max="1000000" :step="100" size="large" class="field-input" style="width: 100%" />
              </a-form-item>
              <a-form-item name="travelers">
                <template #label><span class="field-label">{{ t('home.travelersLabel') }}</span></template>
                <a-input-number v-model:value="formData.travelers" :min="1" :max="oneClickEnabled ? 2 : 20" size="large" class="field-input" style="width: 100%" />
              </a-form-item>
              <a-form-item v-if="!oneClickEnabled" name="pace">
                <template #label><span class="field-label">{{ t('home.paceLabel') }}</span></template>
                <a-select v-model:value="formData.pace" size="large" class="field-select">
                  <a-select-option value="relaxed">{{ t('home.paces.relaxed') }}</a-select-option>
                  <a-select-option value="balanced">{{ t('home.paces.balanced') }}</a-select-option>
                  <a-select-option value="intensive">{{ t('home.paces.intensive') }}</a-select-option>
                </a-select>
              </a-form-item>
              <a-form-item v-if="!oneClickEnabled" name="max_daily_walking_minutes">
                <template #label><span class="field-label">{{ t('home.walkingLimitLabel') }}</span></template>
                <a-input-number v-model:value="formData.max_daily_walking_minutes" :min="0" :max="1440" :step="15" size="large" class="field-input" style="width: 100%" />
              </a-form-item>
            </div>

            <p v-if="oneClickEnabled" class="planning-hint">{{ t('oneClick.budgetHint') }} {{ t('oneClick.returnDate') }}: {{ computedEndDate?.format('YYYY-MM-DD') }}</p>
            <p v-if="oneClickEnabled" class="planning-hint">{{ t('oneClick.optional') }}</p>
            <a-select v-if="pausedTask" v-model:value="restoredMustVisit" mode="tags" :aria-label="t('result.review.addAttractions')" style="width: 100%" />
            <label v-if="oneClickEnabled && formData.transportation === 'flight'"><input v-model="flightConfirmed" type="checkbox" /> {{ t('oneClick.flightConsent') }}</label>
            <details class="planning-preferences" :open="!oneClickEnabled"><summary>{{ t('oneClick.more') }}</summary>
            <div class="grid grid2 daily-time-grid">
              <a-form-item name="daily_start_time">
                <template #label><span class="field-label">{{ t('home.dailyStartLabel') }}</span></template>
                <a-time-picker v-model:value="formData.daily_start_time" format="HH:mm" :minute-step="15" size="large" class="field-input" style="width: 100%" />
              </a-form-item>
              <a-form-item name="daily_end_time">
                <template #label><span class="field-label">{{ t('home.dailyEndLabel') }}</span></template>
                <a-time-picker v-model:value="formData.daily_end_time" format="HH:mm" :minute-step="15" size="large" class="field-input" style="width: 100%" />
              </a-form-item>
            </div>

            </details>
            <a-form-item name="preferences">
              <template #label>
                <span class="field-label">{{ t('home.interestsLabel') }}</span>
              </template>
              <div class="interest-grid">
                <a-checkbox-group v-model:value="formData.preferences" class="interest-group">
                  <label
                    v-for="item in interestOptions"
                    :key="item.value"
                    class="interest-pill"
                    :class="{ active: formData.preferences.includes(item.value) }"
                    @click.prevent="togglePreference(item.value)"
                  >
                    {{ t(item.labelKey) }}
                  </label>
                </a-checkbox-group>
              </div>
            </a-form-item>
          </div>

          <div class="step attraction-discovery-step">
            <div class="discovery-heading">
              <div>
                <div class="step-head">
                  <span>03</span>
                  <h3>{{ t('home.discovery.title') }}</h3>
                </div>
                <p>{{ t('home.discovery.description') }}</p>
              </div>
              <button
                type="button"
                class="discovery-load-btn"
                :disabled="discoveryLoading || loading"
                @click="discoverAttractions"
              >
                {{ discoveryLoading ? t('home.discovery.loading') : t('home.discovery.load') }}
              </button>
            </div>

            <div v-if="candidateCities.length" class="candidate-city-list">
              <section v-for="page in candidateCities" :key="page.city" class="candidate-city-section">
                <div class="candidate-city-head">
                  <div>
                    <strong>{{ page.city }}</strong>
                    <span>{{ t('home.discovery.selected', { count: selectedCount(page.city) }) }}</span>
                  </div>
                  <a-input
                    v-model:value="candidateSearch[page.city]"
                    :placeholder="t('home.discovery.search')"
                    allow-clear
                    class="candidate-search"
                  />
                </div>
                <div v-if="visibleCandidates(page.city).length" class="candidate-grid">
                  <button
                    v-for="candidate in visibleCandidates(page.city)"
                    :key="candidate.poi_id"
                    type="button"
                    class="candidate-card"
                    :class="{ selected: isCandidateSelected(candidate.poi_id) }"
                    :aria-pressed="isCandidateSelected(candidate.poi_id)"
                    @click="toggleCandidate(candidate.poi_id)"
                  >
                    <div class="candidate-image-wrap">
                      <img
                        v-if="candidate.image.url"
                        :src="candidate.image.url"
                        :alt="candidate.name"
                        loading="lazy"
                        referrerpolicy="no-referrer"
                      />
                      <span v-else>{{ t('home.discovery.noImage') }}</span>
                      <i>{{ isCandidateSelected(candidate.poi_id) ? '✓' : '+' }}</i>
                    </div>
                    <div class="candidate-copy">
                      <div>
                        <strong>{{ candidate.name }}</strong>
                        <span v-if="candidate.rating">{{ candidate.rating.toFixed(1) }}</span>
                      </div>
                      <p>{{ candidate.recommendation_reason }}</p>
                      <small>{{ candidate.category }}</small>
                      <a
                        v-if="candidate.image.source_page && candidate.image.attribution"
                        :href="candidate.image.source_page"
                        target="_blank"
                        rel="noopener noreferrer"
                        @click.stop
                      >{{ candidate.image.attribution }}</a>
                    </div>
                  </button>
                </div>
                <div v-else class="candidate-empty">
                  {{ page.degraded ? t('home.discovery.failed') : t('home.discovery.empty') }}
                </div>
                <button
                  v-if="filteredCandidateCount(page.city) > (candidateVisible[page.city] || 8)"
                  type="button"
                  class="candidate-more"
                  @click="candidateVisible[page.city] = (candidateVisible[page.city] || 8) + 8"
                >{{ t('home.discovery.more') }}</button>
              </section>
            </div>
          </div>

          <div class="step">
            <div class="step-head">
              <span>04</span>
              <h3>{{ t('home.step3') }}</h3>
            </div>
            <a-form-item name="free_text_input">
              <div class="field-textarea">
                <a-textarea
                  v-model:value="formData.free_text_input"
                  :placeholder="t('home.specialNeedsPlaceholder')"
                  :rows="4"
                  size="large"
                  class="special-textarea"
                />
              </div>
            </a-form-item>
          </div>

          <a-form-item>
            <button type="submit" class="btn btn-danger btn-round submit-btn" :class="{ loading }" :disabled="loading">
              <span v-if="!loading">{{ t(pausedTask ? 'oneClick.continue' : 'home.submit') }}</span>
              <span v-else class="loading-row">
                <i class="spinner"></i>
                {{ t('home.submitting') }}
              </span>
            </button>
          </a-form-item>
        </a-form>

        <div v-if="failedTask && !loading" class="failure-recovery" role="alert">
          <div>
            <span class="failure-eyebrow">{{ t('home.failure.eyebrow') }}</span>
            <h3>{{ t('home.failure.title') }}</h3>
            <p>{{ failedTask.message }}</p>
            <code>{{ t('home.failure.diagnosticId') }}: {{ failedTask.traceId }}</code>
          </div>
          <button type="button" class="btn btn-danger btn-round retry-btn" @click="handleRetry">
            {{ t('home.failure.retry') }}
          </button>
        </div>

        <!-- Node Loading Stepper -->
        <div v-show="loading" class="stepper-wrapper">
          <div class="stepper-header">
            <h2 class="stepper-title">{{ t('home.loading.planCode', { code: planCode }) }}</h2>
            <p class="stepper-subtitle">{{ t('home.loading.preparing') }}</p>
          </div>
          
          <div class="stepper-container">
            <!-- These thresholds mirror the real JourneyGraph node progress emitted by the worker. -->
            <div class="step-node" :class="{ active: loadingProgress >= 0 && loadingProgress <= 20, completed: loadingProgress > 20 }">
              <div class="node-icon">
                <i v-if="loadingProgress >= 0 && loadingProgress <= 20" class="spinner-small"></i>
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
              </div>
              <p class="node-text">{{ t('home.loading.nodes.request') }}</p>
            </div>
            <div class="step-divider" :class="{ completed: loadingProgress > 20 }"></div>

            <div class="step-node" :class="{ active: loadingProgress > 20 && loadingProgress <= 45, completed: loadingProgress > 45 }">
              <div class="node-icon">
                <i v-if="loadingProgress > 20 && loadingProgress <= 45" class="spinner-small"></i>
                <svg v-else width="20px" height="20px" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path d="M10.5 1.5V3.1M3.6 10H2M5.4512 4.95137L4.31982 3.82M15.5498 4.95137L16.6812 3.82M19 10H17.4M6.50007 10.0001C6.50007 7.79093 8.29093 6.00007 10.5001 6.00007C12.0061 6.00007 13.3177 6.83235 14.0001 8.06206M6 22C3.79086 22 2 20.2091 2 18C2 15.7909 3.79086 14 6 14C6.46419 14 6.90991 14.0791 7.32442 14.2245C8.04061 12.3396 9.86387 11 12 11C14.1361 11 15.9594 12.3396 16.6756 14.2245C17.0901 14.0791 17.5358 14 18 14C20.2091 14 22 15.7909 22 18C22 20.2091 20.2091 22 18 22C13.3597 22 9.87921 22 6 22Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <p class="node-text">{{ t('home.loading.nodes.research') }}</p>
            </div>
            <div class="step-divider" :class="{ completed: loadingProgress > 45 }"></div>

            <div class="step-node" :class="{ active: loadingProgress > 45 && loadingProgress <= 75, completed: loadingProgress > 75 }">
              <div class="node-icon">
                <i v-if="loadingProgress > 45 && loadingProgress <= 75" class="spinner-small"></i>
                <svg v-else fill="currentColor" width="25px" height="25px" viewBox="0 0 24 24" version="1.1" xml:space="preserve" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
                    <g id="Layer_Grid"/><g id="Layer_2">
                    <path d="M21,8c0-2.2-1.8-4-4-4H7C4.8,4,3,5.8,3,8v3.8c-0.6,0.5-1,1.3-1,2.2v2.7V17v2c0,0.6,0.4,1,1,1s1-0.4,1-1v-1h16v1   c0,0.6,0.4,1,1,1s1-0.4,1-1v-2v-0.3V14c0-0.9-0.4-1.7-1-2.2V8z M5,8c0-1.1,0.9-2,2-2h10c1.1,0,2,0.9,2,2v3h-1v-1c0-1.7-1.3-3-3-3   h-1c-0.8,0-1.5,0.3-2,0.8C11.5,7.3,10.8,7,10,7H9c-1.7,0-3,1.3-3,3v1H5V8z M16,10v1h-3v-1c0-0.6,0.4-1,1-1h1C15.6,9,16,9.4,16,10z    M11,10v1H8v-1c0-0.6,0.4-1,1-1h1C10.6,9,11,9.4,11,10z M20,16H4v-2c0-0.6,0.4-1,1-1h3h3h2h3h3c0.6,0,1,0.4,1,1V16z"/></g>
                </svg>
              </div>
              <p class="node-text">{{ t('home.loading.nodes.draft') }}</p>
            </div>
            <div class="step-divider" :class="{ completed: loadingProgress > 75 }"></div>

            <div class="step-node" :class="{ active: loadingProgress > 75 && loadingProgress < 100, completed: loadingProgress >= 100 }">
              <div class="node-icon">
                <i v-if="loadingProgress > 75 && loadingProgress < 100" class="spinner-small"></i>
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
              </div>
              <p class="node-text">{{ t('home.loading.nodes.validate') }}</p>
            </div>
          </div>
          
          <div class="stepper-footer">
            <h3>{{ loadingStatus }}</h3>
            <p v-if="loadingProgress < 100">{{ t('home.loading.workingTogether') }}</p>
            <p v-else>{{ t('home.loading.donePrepare') }}</p>
            <ol v-if="loadingEvents.length" class="node-event-log">
              <li v-for="(event, index) in loadingEvents" :key="`${event.stage}-${event.progress}-${index}`">
                <span>{{ event.progress }}%</span>
                <strong>{{ event.message }}</strong>
              </li>
            </ol>
          </div>
        </div>
      </div>
    </section>

  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, toRaw, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  generateTripPlan,
  getTravelCapabilities, getTripTask, continueTripPlan, readPlanningInput, readTravelQueries, resumeTripPlan,
  getAttractionCandidates,
  resolveAttractionImage,
  retryTripPlan,
  TripTaskFailure,
} from '@/services/api'
import {
  buildCandidateDiscoveryState,
  filterCandidateItems,
  findCandidatePageKey,
  selectedCandidateNames,
  toggleCandidateSelection,
  visibleCandidateItems,
} from '@/services/attractionSelection'
import { getCurrentLocale } from '@/i18n'
import NavBar from '@/components/NavBar.vue'
import heroImage from '@/assets/journeygo-hero.png'
import type {
  AttractionCandidatePage,
  TripFormData,
  TripTaskEvent,
  CityStay,
  TripPlanResponse,
} from '@/types'
import { memoriesState, type LandingFormData } from '@/services/memoriesState'
import dayjs from 'dayjs'

type FailedTask = {
  taskId: string
  traceId: string
  code: string
  message: string
}

const router = useRouter()
const { t } = useI18n()
const oneClickEnabled = ref(false)
const flightConfirmed = ref(false)
const refreshQuote = ref(false)
const pausedTask = ref<{ taskId: string; message: string; provider?: string } | null>(null)
const retainedQueries = ref<any[]>([])
function queryPreview(query: any): string[] {
  const result = query.result
  if (!result || query.status !== 'succeeded') return []
  if (query.provider === 'train' && Array.isArray(result)) return result.slice(0, 3).map(row => `${row.start_train_code} ${row.from_station} → ${row.to_station} ${row.start_time}–${row.arrive_time}`)
  if (query.provider === 'flight') return (result.data || []).slice(0, 3).map((row: any) => `${row.flightno} ${row.depaptcname} → ${row.arraptcname}`)
  if (query.provider === 'hotel') return (result.hotelInformationList || result.roomRatePlans || []).slice(0, 3).map((row: any) => row.name || row.roomName)
  return []
}
const restoredMustVisit = ref<string[]>([])
const restoredConstraints = ref<{ avoid?: string[]; accessibility_needs?: string[] }>({})
onMounted(async () => {
  try {
    oneClickEnabled.value = !!(await getTravelCapabilities()).one_click?.enabled
    if (oneClickEnabled.value) {
      formData.cities = formData.cities.slice(0, 1)
      formData.cities[0].days = Math.max(2, formData.cities[0].days)
      formData.transportation = 'train'
      formData.accommodation = 'business'
      formData.travelers = Math.min(2, formData.travelers)
    }
    const taskId = sessionStorage.getItem('tripTaskId')
    if (!taskId) return
    const task = await getTripTask(taskId)
    if (task.status === 'awaiting_input') {
      pausedTask.value = { taskId, message: task.pending_input?.message || task.message, provider: task.pending_input?.provider }
      retainedQueries.value = await readTravelQueries(taskId)
      const request = await readPlanningInput(task.trip_id)
      restoredMustVisit.value = request.must_visit || []
      restoredConstraints.value = { avoid: request.avoid || [], accessibility_needs: request.accessibility_needs || [] }
      Object.assign(formData, { origin: request.origin, cities: request.destinations,
        start_date: dayjs(request.start_date), transportation: request.intercity_mode,
        accommodation: request.hotel_tier, budget_total: Number(request.budget_total), travelers: request.travelers,
        preferences: request.interests, free_text_input: request.free_text_input,
        daily_start_time: dayjs(request.start_date + 'T' + request.daily_start_time),
        daily_end_time: dayjs(request.start_date + 'T' + request.daily_end_time) })
    } else if (['queued', 'processing', 'retrying'].includes(task.status)) {
      startTaskUi()
      try { applyGeneratedPlan(await resumeTripPlan(taskId, taskCallbacks())) }
      catch (error) { captureTaskFailure(error) }
      finally { finishTaskUi() }
    }
  } catch { /* The classic form remains available if the capability service is unavailable. */ }
})

const loading = ref(false)
const loadingProgress = ref(0)
const loadingStatus = ref('')
const scrollY = ref(0)
const formRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const panelHeight = ref<number | string>('auto')
const fogEnabled = ref(true)
const planCode = ref('')
const loadingEvents = ref<Array<{ stage: string; progress: number; message: string }>>([])
const failedTask = ref<FailedTask | null>(null)
const discoveryLoading = ref(false)
const candidatePages = ref<Record<string, AttractionCandidatePage>>({})
const selectedPoiIds = ref<string[]>([])
const candidateSearch = reactive<Record<string, string>>({})
const candidateVisible = reactive<Record<string, number>>({})
const discoverySignature = ref('')

const getStageStatusText = (stage: TripTaskEvent['stage']) => {
  if (stage && ['query_transport', 'query_hotel', 'plan_places', 'check_trip'].includes(stage)) return t(`oneClick.${stage}`)
  if (stage === 'submitted' || stage === 'initializing') return t('home.loading.initializing')
  if (stage === 'attraction_search') return t('home.loading.searchingAttractions')
  if (stage === 'weather_search') return t('home.loading.queryingWeather')
  if (stage === 'hotel_search') return t('home.loading.recommendingHotels')
  if (stage === 'planning') return t('home.loading.generatingPlan')
  if (stage === 'workflow_start') return t('home.loading.nodes.request')
  if (stage === 'normalize_request') return t('home.loading.normalizing')
  if (stage === 'prepare_research' || stage === 'research_web' || stage === 'collect') return t('home.loading.nodes.research')
  if (stage === 'transport') return t('home.loading.transport')
  if (stage === 'draft') return t('home.loading.drafting')
  if (stage === 'enrich_plan') return t('home.loading.enriching')
  if (stage === 'validate' || stage === 'revise') return t('home.loading.validating')
  if (stage === 'human_review') return t('home.loading.awaitingApproval')
  if (stage === 'persist') return t('home.loading.persisting')
  if (stage === 'graph_building') return t('home.loading.generatingPlan')
  if (stage === 'completed') return t('home.loading.done')
  return t('home.loading.initializing')
}

const interestOptions = [
  { value: '历史文化', labelKey: 'home.interests.history' },
  { value: '自然风光', labelKey: 'home.interests.nature' },
  { value: '美食', labelKey: 'home.interests.food' },
  { value: '购物', labelKey: 'home.interests.shopping' },
  { value: '艺术', labelKey: 'home.interests.art' },
  { value: '休闲', labelKey: 'home.interests.leisure' },
]

const formRules = computed(() => ({
  origin: [{ required: true, whitespace: true, message: t('home.originRequired') }],
  startDate: [{ required: true, message: t('home.startDateRequired') }],
}))

const formData = reactive<LandingFormData>({
  origin: '',
  cities: [{ city: '', days: 2 }],
  start_date: null,
  transportation: '公共交通',
  accommodation: '经济型酒店',
  preferences: [],
  free_text_input: '',
  budget_total: 3000,
  travelers: 1,
  pace: 'balanced',
  daily_start_time: dayjs().hour(9).minute(0).second(0),
  daily_end_time: dayjs().hour(21).minute(0).second(0),
  max_daily_walking_minutes: 180,
})

const totalDays = computed(() => formData.cities.reduce((sum, cs) => sum + (cs.days || 1), 0))
watch(() => [formData.origin, formData.cities[0]?.city, formData.start_date?.format(), totalDays.value, formData.travelers, formData.transportation, refreshQuote.value], () => { flightConfirmed.value = false })

const computedEndDate = computed(() => {
  if (!formData.start_date) return null
  return formData.start_date.add(totalDays.value - 1, 'day')
})

const currentDiscoverySignature = computed(() => JSON.stringify({
  cities: formData.cities
    .filter(item => item.city.trim())
    .map(item => ({ city: item.city.trim(), days: item.days || 1 })),
  interests: [...formData.preferences].sort(),
}))

const candidateCities = computed(() => formData.cities
  .map(item => candidatePages.value[item.city.trim()])
  .filter((page): page is AttractionCandidatePage => Boolean(page)))

const mustVisitNames = computed(() => selectedCandidateNames(candidateCities.value, selectedPoiIds.value))

const isCandidateSelected = (poiId: string) => selectedPoiIds.value.includes(poiId)

const toggleCandidate = (poiId: string) => {
  selectedPoiIds.value = toggleCandidateSelection(selectedPoiIds.value, poiId)
}

const cityCandidates = (city: string) => {
  return filterCandidateItems(candidatePages.value[city], candidateSearch[city] || '')
}

const visibleCandidates = (city: string) => visibleCandidateItems(
  candidatePages.value[city],
  candidateSearch[city] || '',
  candidateVisible[city] || 8,
)
const filteredCandidateCount = (city: string) => cityCandidates(city).length
const selectedCount = (city: string) => {
  const selected = new Set(selectedPoiIds.value)
  return (candidatePages.value[city]?.items || []).filter(item => selected.has(item.poi_id)).length
}

const hydrateCandidateImages = async (pages: AttractionCandidatePage[]) => {
  const pending = pages.flatMap(page => page.items.slice(0, 12).filter(item => !item.image.url))
  const concurrency = 4
  let index = 0
  const worker = async () => {
    while (index < pending.length) {
      const candidate = pending[index++]
      const resolved = await resolveAttractionImage(candidate)
      const pageKey = findCandidatePageKey(candidatePages.value, candidate.poi_id)
      const page = pageKey ? candidatePages.value[pageKey] : undefined
      if (!page) continue
      page.items = page.items.map(item => item.poi_id === resolved.poi_id ? resolved : item)
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, pending.length) }, worker))
}

const discoverAttractions = async () => {
  const cities = formData.cities.filter(item => item.city.trim())
  if (!cities.length) {
    message.error(t('home.atLeastOneCity'))
    return false
  }
  discoveryLoading.value = true
  try {
    const results = await Promise.allSettled(
      cities.map(item => getAttractionCandidates(item.city.trim(), item.days || 1, formData.preferences))
    )
    const discovery = buildCandidateDiscoveryState(cities, results)
    results.forEach((_result, index) => {
      const city = cities[index].city.trim()
      candidateSearch[city] = ''
      candidateVisible[city] = 8
    })
    candidatePages.value = discovery.pages
    selectedPoiIds.value = discovery.selectedPoiIds
    discoverySignature.value = currentDiscoverySignature.value
    void hydrateCandidateImages(Object.values(discovery.pages))
    return true
  } finally {
    discoveryLoading.value = false
  }
}

const addCity = () => {
  if (formData.cities.length >= 5) return
  formData.cities.push({ city: '', days: 2 })
}

const removeCity = (index: number) => {
  if (formData.cities.length <= 1) return
  formData.cities.splice(index, 1)
}

const toneProgress = computed(() => Math.min(Math.max((scrollY.value - 20) / 360, 0), 1))
const lowerShadeStyle = computed(() => ({
  opacity: `${(0.34 + toneProgress.value * 0.52) * (fogEnabled.value ? 1 : 0)}`,
}))
const formRevealStyle = computed(() => {
  const progress = Math.min(Math.max((scrollY.value - 80) / 340, 0), 1)
  return {
    opacity: `${0.2 + progress * 0.8}`,
    transform: `translate3d(0, ${(1 - progress) * 56}px, 0)`,
  }
})

const togglePreference = (value: string) => {
  const index = formData.preferences.indexOf(value)
  if (index === -1) formData.preferences.push(value)
  else formData.preferences.splice(index, 1)
}

const onScroll = () => {
  scrollY.value = window.scrollY || 0
}
const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })
const scrollToForm = () => {
  if (formRef.value) {
    const y = formRef.value.getBoundingClientRect().top + window.scrollY - 65
    window.scrollTo({ top: y, behavior: 'smooth' })
  }
}


const openMemories = () => {
  if (loading.value || discoveryLoading.value) return
  memoriesState.landing = {
    form: { ...toRaw(formData), cities: formData.cities.map(item => ({ ...item })), preferences: [...formData.preferences] },
    candidatePages: toRaw(candidatePages.value),
    selectedPoiIds: [...selectedPoiIds.value],
    candidateSearch: { ...candidateSearch },
    candidateVisible: { ...candidateVisible },
    discoverySignature: discoverySignature.value,
    scrollY: window.scrollY,
  }
  memoriesState.items = null
  memoriesState.scrollY = 0
  void router.push('/history')
}

onMounted(async () => {
  const draft = memoriesState.landing
  if (draft) {
    Object.assign(formData, draft.form)
    candidatePages.value = draft.candidatePages
    selectedPoiIds.value = draft.selectedPoiIds
    Object.assign(candidateSearch, draft.candidateSearch)
    Object.assign(candidateVisible, draft.candidateVisible)
    discoverySignature.value = draft.discoverySignature
    memoriesState.landing = null
    await nextTick()
    window.scrollTo({ top: draft.scrollY, behavior: 'instant' })
  }
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})

const startTaskUi = () => {
  if (panelRef.value) panelHeight.value = panelRef.value.offsetHeight
  loading.value = true
  loadingProgress.value = 5
  loadingStatus.value = t('home.loading.initializing')
  loadingEvents.value = []
  failedTask.value = null
}

const taskCallbacks = () => ({
  onTaskCreated: (task: { task_id: string; trip_id: string; trace_id: string; plan_id: string }) => {
    planCode.value = task.plan_id || task.task_id
    sessionStorage.setItem('tripTaskId', task.task_id)
    sessionStorage.setItem('tripId', task.trip_id)
    loadingProgress.value = 5
    loadingStatus.value = t('home.loading.initializing')
  },
  onTaskEvent: (event: TripTaskEvent) => {
    if (event.status === 'awaiting_input') {
      pausedTask.value = { taskId: event.task_id, message: event.pending_input?.message || event.message, provider: event.pending_input?.provider }
      readTravelQueries(event.task_id).then(value => { retainedQueries.value = value }).catch(() => {})
    }
    if (event.plan_id) planCode.value = event.plan_id
    if (Number.isFinite(event.progress)) {
      loadingProgress.value = Math.max(0, Math.min(100, event.progress))
    }
    const translated = getStageStatusText(event.stage)
    loadingStatus.value = translated || event.message
    const previous = loadingEvents.value[loadingEvents.value.length - 1]
    if (!previous || previous.stage !== event.stage || previous.progress !== event.progress) {
      loadingEvents.value = [
        ...loadingEvents.value,
        { stage: event.stage, progress: event.progress, message: translated || event.message },
      ].slice(-6)
    }
  },
})

const applyGeneratedPlan = (response: TripPlanResponse) => {
  if (!response.success || !response.data) {
    throw new Error(response.message || t('home.messages.generateFailed'))
  }
  const generatedPlanId = response.plan_id || response.task_id || planCode.value
  loadingProgress.value = 100
  loadingStatus.value = t('home.loading.done')
  sessionStorage.setItem('tripPlan', JSON.stringify(response.data))
  if (response.graph_data) sessionStorage.setItem('graphData', JSON.stringify(response.graph_data))
  if (generatedPlanId) sessionStorage.setItem('planId', generatedPlanId)
  if (response.task_id) sessionStorage.setItem('tripTaskId', response.task_id)
  if (response.trip_id) sessionStorage.setItem('tripId', response.trip_id)
  if (response.review) sessionStorage.setItem('tripReview', JSON.stringify(response.review))
  message.success(
    response.review?.status === 'pending'
      ? t('home.messages.awaitingApproval')
      : t('home.messages.generateSuccess')
  )
  setTimeout(() => {
    router.push({
      path: '/result',
      query: {
        ...(generatedPlanId ? { plan_id: generatedPlanId } : {}),
        ...(response.task_id ? { task_id: response.task_id } : {}),
      },
    })
  }, 500)
}

const captureTaskFailure = (error: unknown) => {
  if (error instanceof TripTaskFailure && error.code === 'awaiting_input') {
    message.info(error.message)
    return
  }
  if (error instanceof TripTaskFailure) {
    failedTask.value = {
      taskId: error.taskId,
      traceId: error.traceId,
      code: error.code,
      message: error.message,
    }
  }
  const userMessage = error instanceof Error ? error.message : t('home.messages.generateRetry')
  message.error(userMessage)
}

const finishTaskUi = () => {
  setTimeout(() => {
    loading.value = false
    loadingProgress.value = 0
    loadingStatus.value = ''
    panelHeight.value = 'auto'
  }, 700)
}

const handleSubmit = async () => {
  if (loading.value) return
  if (oneClickEnabled.value && formData.transportation === 'flight' && !flightConfirmed.value) {
    message.warning(t('oneClick.flightConsent'))
    return
  }
  if (!formData.origin.trim()) {
    message.error(t('home.originRequired'))
    return
  }
  // 校验：至少一个城市名非空
  const validCities = formData.cities.filter(cs => cs.city.trim())
  if (validCities.length === 0) {
    message.error(t('home.atLeastOneCity'))
    return
  }
  if (!formData.start_date) {
    message.error(t('home.messages.selectDate'))
    return
  }
  if (totalDays.value > 30) {
    message.warning(t('home.messages.travelDaysTooLong'))
    return
  }
  if (!formData.daily_end_time.isAfter(formData.daily_start_time)) {
    message.warning(t('home.messages.dailyTimeInvalid'))
    return
  }

  if (!oneClickEnabled.value && discoverySignature.value !== currentDiscoverySignature.value) {
    await discoverAttractions()
    message.info(t('home.discovery.reviewBeforePlan'))
    return
  }

  startTaskUi()
  planCode.value = ''

  try {
    sessionStorage.removeItem('tripPlan')
    sessionStorage.removeItem('graphData')
    sessionStorage.removeItem('planId')
    sessionStorage.removeItem('tripReview')

    const citiesPayload: CityStay[] = validCities.map(cs => ({ city: cs.city.trim(), days: cs.days || 1 }))
    const endDate = computedEndDate.value!

    const requestData: TripFormData = {
      planning_mode: oneClickEnabled.value ? 'one_click' : 'classic',
      intercity_mode: formData.transportation === 'flight' ? 'flight' : 'train',
      hotel_tier: ['economy', 'premium'].includes(formData.accommodation) ? formData.accommodation as 'economy' | 'premium' : 'business',
      flight_confirmed: flightConfirmed.value,
      origin: formData.origin.trim(),
      city: citiesPayload[0].city,
      cities: citiesPayload,
      start_date: formData.start_date.format('YYYY-MM-DD'),
      end_date: endDate.format('YYYY-MM-DD'),
      travel_days: totalDays.value,
      transportation: formData.transportation,
      accommodation: formData.accommodation,
      preferences: formData.preferences,
      must_visit: [...new Set([...mustVisitNames.value, ...restoredMustVisit.value])],
      avoid: restoredConstraints.value.avoid,
      accessibility_needs: restoredConstraints.value.accessibility_needs,
      free_text_input: formData.free_text_input,
      language: getCurrentLocale(),
      budget_total: formData.budget_total,
      currency: 'CNY',
      travelers: formData.travelers,
      pace: oneClickEnabled.value ? 'balanced' : formData.pace,
      daily_start_time: formData.daily_start_time.format('HH:mm:ss'),
      daily_end_time: formData.daily_end_time.format('HH:mm:ss'),
      max_daily_walking_minutes: oneClickEnabled.value ? undefined : formData.max_daily_walking_minutes,
    }

    const paused = pausedTask.value
    applyGeneratedPlan(await (paused
      ? continueTripPlan(requestData, paused.taskId, refreshQuote.value ? paused.provider : undefined, taskCallbacks())
      : generateTripPlan(requestData, taskCallbacks())))
    pausedTask.value = null
  } catch (error: unknown) {
    sessionStorage.removeItem('tripPlan')
    sessionStorage.removeItem('graphData')
    sessionStorage.removeItem('planId')
    captureTaskFailure(error)
  } finally {
    flightConfirmed.value = false
    finishTaskUi()
  }
}

const handleRetry = async () => {
  const task = failedTask.value
  if (!task) return
  startTaskUi()
  planCode.value = task.taskId
  try {
    applyGeneratedPlan(await retryTripPlan(task.taskId, taskCallbacks()))
  } catch (error: unknown) {
    captureTaskFailure(error)
    if (!failedTask.value) failedTask.value = task
  } finally {
    finishTaskUi()
  }
}
</script>

<style scoped>
.landing-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0d171d 0%, #142430 58%, #0f1a22 100%);
  color: #ecf3fa;
  position: relative;
  isolation: isolate;
  overflow-x: hidden; /* 防止水平溢出导致的出界感 */
}

.lower-shade {
  position: fixed;
  inset: 0% 0 -1px 0;
  z-index: 0;
  pointer-events: none;
  background: rgba(6, 14, 20, 0.7);
  transition: opacity 0.18s linear;
}

.lower-shade::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: -28px;
  height: 28px;
  background: linear-gradient(to bottom, rgba(6, 14, 20, 0), rgba(6, 14, 20, 0.92));
}

.journey-hero {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  min-height: 720px;
  height: 100svh;
  max-height: 1100px;
  display: flex;
  align-items: center;
  background-size: cover;
  background-position: center;
  color: #fff9ed;
}
.journey-landscape, .journey-mist, .journey-sunlight {
  position: absolute;
  inset: 0;
  z-index: -3;
  pointer-events: none;
}
.journey-landscape {
  background-size: cover;
  background-position: center;
  transform-origin: 68% 42%;
  animation: landscape-drift 20s ease-in-out -5s infinite alternate;
}
.journey-mist {
  inset: 30% -12% 34% 40%;
  z-index: -2;
  mask-image: radial-gradient(ellipse at center, #000 25%, transparent 70%);
  background: radial-gradient(ellipse at 22% 65%, rgba(218, 233, 239, .44), transparent 48%), radial-gradient(ellipse at 65% 38%, rgba(244, 236, 213, .34), transparent 42%), radial-gradient(ellipse at 88% 72%, rgba(218, 233, 239, .3), transparent 38%);
  animation: valley-mist 14s ease-in-out -4s infinite alternate;
}
.journey-sunlight {
  inset: -4%;
  z-index: -2;
  background: radial-gradient(ellipse at 100% 18%, rgba(255, 203, 125, .42), transparent 48%), conic-gradient(from 200deg at 100% 18%, transparent 0deg, rgba(255, 221, 158, .12) 12deg, transparent 24deg, rgba(255, 221, 158, .08) 36deg, transparent 48deg);
  animation: sunset-glow 10s ease-in-out -3s infinite alternate;
}
@keyframes landscape-drift { from { transform: scale(1); } to { transform: scale(1.10) translate3d(-.7%, .3%, 0); } }
@keyframes valley-mist { from { transform: translate3d(-12%, 3%, 0); opacity: .45; } to { transform: translate3d(12%, -3%, 0); opacity: .9; } }
@keyframes sunset-glow { from { opacity: .35; transform: translate3d(0, 0, 0); } to { opacity: .85; transform: translate3d(-2%, 1%, 0); } }
.journey-hero-shade {
  position: absolute;
  inset: 0;
  z-index: -1;
  background: linear-gradient(90deg, rgba(9, 26, 36, .74), rgba(9, 26, 36, .38) 36%, transparent 65%), linear-gradient(0deg, #0b151d 0%, transparent 18%);
}
.journey-hero-content {
  width: 40%;
  margin-left: 7%;
  padding: 110px 0 150px;
  animation: trail-reveal .7s ease-out both;
}
.journey-hero h1 {
  margin: 0 0 26px;
  color: #ffe2a9;
  font-family: 'Noto Serif SC', 'Songti SC', 'SimSun', Georgia, serif;
  font-size: clamp(40px, 4.2vw, 72px);
  font-weight: 600;
  letter-spacing: .04em;
  line-height: 1.2;
}
.journey-hero-copy {
  margin: 0 0 38px;
  color: #fff9ed;
  font-size: clamp(23px, 2.3vw, 38px);
  line-height: 1.65;
  font-weight: 400;
  text-shadow: 0 2px 20px #10273788;
}
.journey-explore {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 40px;
  margin-top: 0;
  padding: 17px 27px;
  border: 1px solid #f5cb87;
  border-radius: 6px;
  background: #f5cb87;
  color: #1b3035;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}
.journey-explore:hover { background: #ffe1ad; }
.journey-explore:focus-visible { outline: 3px solid white; outline-offset: 4px; }
.journey-hero button:disabled { opacity: .55; cursor: wait; }
@keyframes trail-reveal { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 760px) {
  .journey-explore { gap: 10px; padding: 10px 14px; font-size: 14px; }
  .journey-landscape {
    inset: 0;
    animation: none;
    background-size: cover;
    background-position: 80% center;
    background-repeat: no-repeat;
  }
  .journey-mist { inset: 35% -8% 42% 15%; }
  .journey-hero {
    min-height: 640px;
    height: 100svh;
    align-items: flex-start;
  }
  .journey-hero-shade {
    inset: 0;
    background: linear-gradient(90deg, #091a3699, #091a3622), linear-gradient(0deg, #0b151d, transparent 28%);
  }
  .journey-hero-content { width: 86%; margin-left: 7%; padding: 130px 0 160px; }
  .journey-hero h1 { font-size: clamp(36px, 9vw, 52px); margin-bottom: 20px; }
  .journey-hero-copy { font-size: 25px; margin-bottom: 28px; }
}
@media (prefers-reduced-motion: reduce) {
  .journey-hero-content, .journey-landscape, .journey-mist, .journey-sunlight { animation: none; }
  .journey-mist { opacity: .45; }
  .journey-sunlight { opacity: .3; }
}

.landing-header {
  /* 确保 hero 区域占满全屏高度，背景图不重复 */
  height: 100vh;
  min-height: 100vh;
  position: relative;
  display: block;
  background-size: cover !important;
  background-repeat: no-repeat !important;
  background-position: center center !important;
  overflow: hidden;
  z-index: 1;
}


.landing-header .content-center {
  margin-top: 0 !important;
  height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 内容垂直居中，确保在 .filter::after 霁罩和 hero-bottom-shade 之上 */
  position: relative;
  z-index: 3;
}

.landing-header .content-center .container {
  transform: translate3d(0, 45px, 0);
}

/* moving-clouds: 依赖 global.css 的定位 (bottom:0, width:250em, cloudLoop 80s) */
/* .landing-header .moving-clouds {
  transition: opacity 0.2s ease;
  pointer-events: none;
  z-index: 2;
} */

/* fog-low: 依赖 global.css 的定位 (margin-left:-35%, width:110%, bottom:0) */
.fog-low {
  pointer-events: none;
  z-index: 2;
  transition: opacity 0.2s ease;
  /* margin-bottom: -35px; */
}

/* fog-low.right: 依赖 global.css 的 margin-left:30%; opacity:1 */

.landing-hero-badge {
  margin: 0 0 18px;
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(236, 243, 250, 0.78);
}

.landing-header .presentation-title {
  font-size: clamp(44px, 7vw, 90px);
  font-weight: 800;
}

.landing-header .presentation-subtitle {
  max-width: 620px;
  /* margin: 22px auto 0; */
  color: rgba(224, 233, 242, 0.78);
  font-size: clamp(15px, 1.8vw, 19px);
  line-height: 1.75;
  /* font-weight: 500; */
  justify-self: center;
}

.hero-bottom-shade {
  position: absolute;
  inset: auto 0 0 0;
  height: 56%;
  z-index: 1;
  pointer-events: none;
  background: linear-gradient(
    to top,
    rgba(6, 14, 20, 0.92) 0%,
    rgba(6, 14, 20, 0.66) 46%,
    rgba(6, 14, 20, 0) 100%
  );
  transition: opacity 0.18s linear;
}


.form-section {
  margin-top: -112px;
  padding: 0 20px 86px;
  position: relative;
  z-index: 3;
}

.form-panel {
  max-width: 1000px;
  margin: 0 auto;
  border: 1.2px solid rgba(236, 243, 250, 0.2);
  border-radius: 22px;
  background: rgba(12, 23, 32, 0.56);
  backdrop-filter: blur(18px);
  box-shadow: 0 24px 80px rgba(4, 11, 18, 0.52);
  padding: 20px;
  transition: 0.25s;
}

.step {
  margin-bottom: 8px;
}

.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.step-head span {
  width: 26px;
  height: 23px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(215, 110, 66, 0.2);
  border: 1.2px solid rgba(215, 110, 66, 0.4);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.step-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
}

.grid {
  display: grid;
  gap: 12px;
}

.grid4 {
  grid-template-columns: 1.5fr 1fr 1fr 0.8fr;
}

.grid-date {
  grid-template-columns: 1fr 0.6fr;
  margin-top: 12px;
}

.grid2 {
  grid-template-columns: 1fr 1fr;
}

.constraint-grid,
.daily-time-grid {
  margin-top: 12px;
}

.city-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 4px;
}

.city-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.city-row-name {
  flex: 2;
  margin-bottom: 0;
}

.city-row-days {
  flex: 0.8;
  margin-bottom: 0;
}

.city-remove-btn {
  flex-shrink: 0;
  width: 36px;
  height: 40px;
  margin-bottom: 0;
  border: 1.2px solid rgba(236, 243, 250, 0.2);
  border-radius: 10px;
  background: rgba(14, 27, 38, 0.66);
  color: rgba(236, 243, 250, 0.6);
  font-size: 18px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.city-remove-btn:hover {
  border-color: rgba(255, 100, 100, 0.6);
  color: #ff6464;
  background: rgba(255, 100, 100, 0.1);
}

.city-add-btn {
  align-self: flex-start;
  padding: 6px 16px;
  border: 1.2px dashed rgba(215, 110, 66, 0.5);
  border-radius: 10px;
  background: transparent;
  color: rgba(215, 110, 66, 0.85);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.city-add-btn:hover {
  border-color: rgba(215, 110, 66, 0.9);
  background: rgba(215, 110, 66, 0.1);
  color: #d76e42;
}

.field-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #fff;
}

.planning-hint,
.planning-preferences,
.planning-preferences summary {
  color: #fff;
}

.planning-hint { line-height: 1.7; }
.planning-preferences summary { cursor: pointer; padding: 10px 0; }

.field-input.ant-input,
.field-input.ant-input-lg,
.field-input.ant-input-number,
.field-input.ant-input-number-lg,
.field-input.ant-picker,
.field-select :deep(.ant-select-selector),
.field-textarea :deep(textarea),
.field-textarea :deep(.ant-input),
.field-textarea.ant-input,
.special-textarea.ant-input {
  border: 1.2px solid rgba(236, 243, 250, 0.2) !important;
  border-radius: 12px !important;
  background: rgba(14, 27, 38, 0.66) !important;
  background-color: rgba(14, 27, 38, 0.66) !important;
  background-image: none !important;
  color: #ecf3fa !important;
}

/* 浏览器自动填充（Autofill）背景色修复 */
:deep(.field-input.ant-input:-webkit-autofill),
:deep(.field-input.ant-input:-webkit-autofill:hover),
:deep(.field-input.ant-input:-webkit-autofill:focus),
:deep(.field-input.ant-input:-webkit-autofill:active),
:deep(.field-input .ant-picker-input > input:-webkit-autofill),
:deep(.field-textarea textarea:-webkit-autofill),
:deep(.special-textarea:-webkit-autofill) {
  -webkit-box-shadow: 0 0 0 1000px #0e1b26 inset !important;
  -webkit-text-fill-color: #ecf3fa !important;
  transition: background-color 5000s ease-in-out 0s !important;
}

.field-input.ant-input-number :deep(.ant-input-number-input),
.field-input.ant-input-number :deep(.ant-input-number-handler-wrap) {
  color: #ecf3fa !important;
}

.field-input.ant-input::placeholder,
:deep(.field-input .ant-picker-input > input::placeholder),
.field-textarea :deep(textarea::placeholder),
.field-textarea.ant-input::placeholder {
  color: rgba(228, 236, 245, 0.4) !important;
}

.field-input.ant-input:hover,
.field-input.ant-picker:hover,
.field-select:hover :deep(.ant-select-selector),
.field-textarea :deep(textarea:hover),
.field-textarea.ant-input:hover {
  border-color: rgba(236, 243, 250, 0.42) !important;
}

.field-input.ant-input:focus,
.field-input.ant-picker-focused,
.field-textarea :deep(textarea:focus),
.field-textarea.ant-input:focus {
  border-color: rgba(215, 110, 66, 0.88) !important;
  box-shadow: 0 0 0 3px rgba(215, 110, 66, 0.2) !important;
  background: rgba(14, 27, 38, 0.66) !important;
  outline: none !important;
}

:deep(.field-input .ant-picker-input > input),
.field-select :deep(.ant-select-selection-item),
:deep(.field-input .ant-picker-suffix),
:deep(.field-input .ant-picker-clear),
.field-select :deep(.ant-select-arrow) {
  color: #ecf3fa !important;
}

.days-chip {
  min-height: 40px;
  border-radius: 12px;
  border: 1.2px solid rgba(215, 110, 66, 0.42);
  background: rgba(19, 34, 46, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.days-number {
  color: rgba(236, 243, 250, 0.72);
  font-size: 18px;
  line-height: 1;
  font-weight: 700;
}

.days-unit {
  font-size: 16px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(224, 233, 242, 0.74);
  font-weight: 700;
}

.interest-grid {
  width: 100%;
}

.interest-group {
  display: grid !important;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  width: 100%;
}

.interest-group :deep(.ant-checkbox-wrapper) {
  display: none !important;
}

.interest-pill {
  min-height: 38px;
  border-radius: 10px;
  border: 1.2px solid rgba(236, 243, 250, 0.16);
  background: rgba(15, 28, 38, 0.6);
  color: #fff;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  user-select: none;
  transition: all 0.55s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.interest-pill:hover {
  background: rgba(236, 243, 250, 0.08);
  border-color: rgba(236, 243, 250, 0.3);
  /* transform: translateY(-2px); */
  box-shadow: 0 4px 12px rgba(4, 11, 18, 0.3);
}

.interest-pill:active {
  transform: translateY(1px) scale(0.96);
  box-shadow: 0 2px 4px rgba(4, 11, 18, 0.2);
}

.interest-pill.active {
  border-color: rgba(215, 110, 66, 0.8);
  background: rgba(215, 110, 66, 0.2);
}

.interest-pill.active:hover {
  background: rgba(215, 110, 66, 0.28);
  border-color: rgba(215, 110, 66, 1);
}

.attraction-discovery-step {
  margin: 18px 0 22px;
  padding: 18px;
  border: 1px solid rgba(215, 110, 66, 0.3);
  border-radius: 16px;
  background: rgba(7, 17, 24, 0.42);
}

.discovery-heading,
.candidate-city-head,
.candidate-city-head > div,
.candidate-copy > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.discovery-heading > div > p {
  margin: -2px 0 0;
  color: #fff;
  font-size: 12px;
}

.discovery-load-btn,
.candidate-more {
  flex: 0 0 auto;
  border: 1px solid rgba(215, 110, 66, 0.55);
  border-radius: 10px;
  background: rgba(215, 110, 66, 0.16);
  color: #fff;
  padding: 9px 14px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.discovery-load-btn:disabled {
  cursor: wait;
  opacity: 0.55;
}

.candidate-city-list {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

.candidate-city-section {
  padding-top: 15px;
  border-top: 1px solid rgba(236, 243, 250, 0.12);
}

.candidate-city-head {
  margin-bottom: 12px;
}

.candidate-city-head > div {
  justify-content: flex-start;
}

.candidate-city-head strong {
  color: #f4f8fc;
  font-size: 15px;
}

.candidate-city-head span {
  color: #e79a78;
  font-size: 12px;
}

.candidate-search {
  width: min(300px, 42%);
}

.candidate-search :deep(.ant-input),
.candidate-search :deep(.ant-input-affix-wrapper) {
  background: rgba(14, 27, 38, 0.72) !important;
  border-color: rgba(236, 243, 250, 0.18) !important;
  color: #ecf3fa !important;
}

.candidate-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.candidate-card {
  overflow: hidden;
  padding: 0;
  border: 1px solid rgba(236, 243, 250, 0.14);
  border-radius: 13px;
  background: rgba(14, 27, 38, 0.72);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s, background 0.2s;
}

.candidate-card:hover {
  transform: translateY(-2px);
  border-color: rgba(236, 243, 250, 0.34);
}

.candidate-card.selected {
  border-color: rgba(215, 110, 66, 0.9);
  background: rgba(69, 38, 28, 0.72);
}

.candidate-image-wrap {
  position: relative;
  aspect-ratio: 16 / 10;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: linear-gradient(135deg, #1b2b36, #0c151c);
  color: rgba(236, 243, 250, 0.42);
  font-size: 12px;
}

.candidate-image-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.candidate-image-wrap i {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(5, 13, 19, 0.8);
  color: #fff;
  font-style: normal;
  font-weight: 800;
}

.candidate-card.selected .candidate-image-wrap i {
  background: #d76e42;
}

.candidate-copy {
  padding: 10px;
}

.candidate-copy strong {
  overflow: hidden;
  color: #f4f8fc;
  font-size: 13px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.candidate-copy > div > span {
  color: #f4b08d;
  font-size: 12px;
}

.candidate-copy p,
.candidate-copy small,
.candidate-copy a {
  display: block;
  overflow: hidden;
  margin: 5px 0 0;
  color: rgba(228, 236, 245, 0.58);
  font-size: 11px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.candidate-copy a {
  color: rgba(231, 154, 120, 0.78);
}

.candidate-empty {
  padding: 28px 12px;
  border: 1px dashed rgba(236, 243, 250, 0.16);
  border-radius: 12px;
  color: rgba(228, 236, 245, 0.54);
  text-align: center;
  font-size: 12px;
}

.candidate-more {
  display: block;
  margin: 12px auto 0;
  background: transparent;
}

.submit-btn {
  color: #fff !important;
  width: 100%;
  min-height: 48px;
  border-radius: 12px;
  /* border: 1px solid rgba(236, 243, 250, 0.28);
  background: linear-gradient(135deg, #d76e42, #a14625);
  color: #fff; */
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
}

.submit-btn.loading {
  background: rgba(14, 27, 38, 0.66);
  cursor: wait;
}

.failure-recovery {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin: 8px 0 22px;
  padding: 22px;
  border: 1px solid rgba(255, 148, 120, 0.48);
  border-radius: 16px;
  background: rgba(96, 35, 28, 0.26);
}

.failure-eyebrow {
  color: #ff9478;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.failure-recovery h3 {
  margin: 5px 0 6px;
  color: #fff;
}

.failure-recovery p {
  margin: 0 0 8px;
  color: rgba(236, 243, 250, 0.72);
}

.failure-recovery code {
  color: #ffd6cc;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.retry-btn {
  flex: 0 0 auto;
}

.loading-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 2px solid rgba(236, 243, 250, 0.24);
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
}

.spinner-small {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2.5px solid rgba(215, 110, 66, 0.24);
  border-top-color: #d76e42;
  animation: spin 0.8s linear infinite;
}

/* 节点动画相关样式 */
.stepper-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 480px;
  animation: fadeIn 0.4s ease;
  padding: 30px 20px;
  box-sizing: border-box;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.stepper-header {
  text-align: center;
  margin-bottom: 50px;
}

.stepper-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 8px;
  letter-spacing: 0.05em;
}

.stepper-subtitle {
  font-size: 15px;
  color: rgba(236, 243, 250, 0.54);
}

.stepper-container {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  width: 100%;
  max-width: 680px;
  margin: 0 auto 50px auto;
}

.step-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100px;
  z-index: 2;
}

.node-icon {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(14, 27, 38, 0.8);
  border: 1.5px solid rgba(236, 243, 250, 0.16);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  color: rgba(236, 243, 250, 0.4);
  transition: all 0.35s ease;
}

.step-node.active .node-icon {
  border-color: #d76e42;
  background: rgba(215, 110, 66, 0.14);
  color: #d76e42;
  box-shadow: 0 0 16px rgba(215, 110, 66, 0.25);
}

.step-node.completed .node-icon {
  background: #d76e42;
  border-color: #d76e42;
  color: #fff;
  box-shadow: 0 0 12px rgba(215, 110, 66, 0.3);
}

.node-text {
  font-size: 12px;
  font-weight: 600;
  color: rgba(236, 243, 250, 0.4);
  text-align: center;
  transition: color 0.35s ease;
  line-height: 1.3;
}

.step-node.active .node-text {
  color: #d76e42;
}

.step-node.completed .node-text {
  color: rgba(236, 243, 250, 0.85);
}

.step-divider {
  flex: 1;
  height: 3px;
  background: rgba(236, 243, 250, 0.08);
  margin-top: 25px; /* (52px / 2) - 1.5px */
  border-radius: 2px;
  position: relative;
  overflow: hidden;
}

.step-divider::after {
  content: '';
  position: absolute;
  top: 0; left: 0; bottom: 0; width: 0%;
  background: #d76e42;
  transition: width 0.45s ease;
}

.step-divider.completed::after {
  width: 100%;
}

.stepper-footer {
  text-align: center;
  margin-top: 10px;
}

.stepper-footer h3 {
  font-size: 20px;
  font-weight: 600;
  color: #d76e42;
  margin-bottom: 8px;
}

.stepper-footer p {
  font-size: 14px;
  color: rgba(236, 243, 250, 0.54);
}

.node-event-log {
  width: min(620px, 100%);
  margin: 18px auto 0;
  padding: 0;
  list-style: none;
  text-align: left;
}

.node-event-log li {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(236, 243, 250, 0.08);
  color: rgba(236, 243, 250, 0.68);
  font-size: 12px;
}

.node-event-log span {
  color: #d76e42;
  font-variant-numeric: tabular-nums;
}

:deep(.ant-form-item-label > label) {
  color: transparent !important;
}

:deep(.ant-form-item-explain-error) {
  color: #ff9478 !important;
}

/* @keyframes cloudLoop {
  from {
    transform: translate3d(0, 0, 0);
  }
  to {
    transform: translate3d(-50%, 0, 0);
  }
} */

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1080px) {
  .grid4 {
    grid-template-columns: 1fr 1fr;
  }

  .interest-group {
    grid-template-columns: repeat(3, 1fr);
  }

  .candidate-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 991px) {
  .form-section {
    padding: 0 14px 72px;
  }

  .form-panel {
    padding: 22px 18px;
  }

  .grid4,
  .grid2,
  .grid-date {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .failure-recovery {
    align-items: stretch;
    flex-direction: column;
  }

  .landing-header .presentation-title {
    font-size: clamp(34px, 10vw, 52px);
  }

  .landing-header .presentation-subtitle {
    font-size: 14px;
    padding: 0 10px;
  }

  .landing-header .content-center .container {
    transform: translate3d(0, 16px, 0);
  }

  .interest-group {
    grid-template-columns: repeat(2, 1fr);
  }

  .attraction-discovery-step {
    padding: 13px;
  }

  .discovery-heading,
  .candidate-city-head {
    align-items: stretch;
    flex-direction: column;
  }

  .discovery-load-btn,
  .candidate-search {
    width: 100%;
  }

  .candidate-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
