<template>
  <section class="trip-navigator" :aria-label="t('navigation.title')">
    <header>
      <h2>{{ t('navigation.title') }}</h2>
      <select v-model="selectedDay" :aria-label="t('navigation.chooseDay')">
        <option v-for="(day, index) in plan.days" :key="index" :value="index">
          {{ day.date }} · {{ day.city || plan.city }}{{ day.date === today ? ` · ${t('navigation.today')}` : '' }}
        </option>
      </select>
    </header>
    <p class="navigator-note">{{ t('navigation.notice') }}</p>
    <p v-if="!day?.timeline?.length" class="navigator-note">{{ t('navigation.noTimeline') }}</p>
    <p v-if="storageFailed" role="status">{{ t('navigation.storageFailed') }}</p>
    <div v-if="nextStop" class="next-stop">
      <span>{{ t('navigation.next') }} <small v-if="nextStop.time">{{ nextStop.time }}</small></span>
      <h3>{{ nextStop.name }}</h3>
      <p>{{ nextStop.address }}</p>
      <PlaceNavigation :place="nextStop" :city="day?.city || plan.city" />
      <div class="progress-actions">
        <button type="button" @click="setStatus(nextStop.id, 'done')">{{ t('navigation.done') }}</button>
        <button type="button" @click="setStatus(nextStop.id, 'skipped')">{{ t('navigation.skip') }}</button>
      </div>
    </div>
    <p v-else role="status">{{ t(stops.length ? 'navigation.complete' : 'navigation.empty') }}</p>
    <details>
      <summary>{{ t('navigation.allStops', { count: stops.length }) }}</summary>
      <ol>
        <li v-for="(stop, index) in stops" :key="stop.id">
          <div class="stop-heading"><strong>{{ stop.name }}</strong><span>{{ stop.time }}</span></div>
          <span v-if="progress[stop.id]">{{ t(`navigation.${progress[stop.id]}`) }}</span>
          <PlaceNavigation :place="stop" :city="day?.city || plan.city" :from="stops[index - 1]" />
          <div class="progress-actions">
            <template v-if="!progress[stop.id]">
              <button type="button" @click="setStatus(stop.id, 'done')">{{ t('navigation.done') }}</button>
              <button type="button" @click="setStatus(stop.id, 'skipped')">{{ t('navigation.skip') }}</button>
            </template>
            <button v-else type="button" @click="setStatus(stop.id)">{{ t('navigation.undo') }}</button>
          </div>
        </li>
      </ol>
    </details>
    <small>{{ t('navigation.localOnly') }}</small>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TripPlan } from '@/types'
import { dayStops, parseProgress, progressKey, type StopStatus } from '@/services/navigation'
import PlaceNavigation from './PlaceNavigation.vue'
const props = defineProps<{ plan: TripPlan; planId: string }>()
const { t } = useI18n()
const now = new Date()
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
const selectedDay = ref(0)
watch(() => [props.planId, props.plan.start_date, props.plan.end_date], () => {
  selectedDay.value = Math.max(0, props.plan.days.findIndex(day => day.date === today))
}, { immediate: true })
const day = computed(() => props.plan.days[selectedDay.value])
const stops = computed(() => day.value ? dayStops(day.value) : [])
const key = computed(() => day.value ? progressKey(props.planId, day.value) : '')
const progress = ref<Record<string, StopStatus>>({})
const storageFailed = ref(false)
watch(key, value => {
  try {
    progress.value = parseProgress(localStorage.getItem(value), stops.value)
    storageFailed.value = false
  } catch {
    progress.value = {}
    storageFailed.value = true
  }
}, { immediate: true })
const nextStop = computed(() => stops.value.find(stop => !progress.value[stop.id]))
function setStatus(id: string, status?: StopStatus) {
  const updated = { ...progress.value }
  if (status) updated[id] = status
  else delete updated[id]
  progress.value = updated
  try {
    localStorage.setItem(key.value, JSON.stringify(updated))
    storageFailed.value = false
  } catch { storageFailed.value = true }
}
</script>

<style scoped>
.trip-navigator { padding: 20px; margin-bottom: 24px; border: 1px solid var(--jg-border); border-radius: 16px; background: var(--jg-surface); color: inherit; }
header, .stop-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
h2, h3 { color: inherit; margin: 0; }
h2 { font-size: 22px; line-height: 1.35; }
h3 { margin-top: 8px; font-size: 24px; }
select { max-width: 100%; min-height: 44px; border-radius: 8px; padding: 8px; background: var(--jg-surface); color: var(--jg-text); border: 1px solid var(--jg-border); }
.navigator-note, small { opacity: .75; font-size: 16px; }
.next-stop { border-left: 3px solid var(--jg-border); padding: 12px 16px; margin: 16px 0; }
.progress-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
button { min-height: 44px; border: 1px solid var(--jg-border); border-radius: 8px; padding: 8px 12px; background: transparent; color: inherit; cursor: pointer; font: inherit; }
button:focus-visible, summary:focus-visible, select:focus-visible { outline: 2px solid var(--jg-accent); outline-offset: 2px; }
summary { cursor: pointer; padding: 12px 0; }
ol { padding-left: 24px; }
li { padding: 12px 0; border-bottom: 1px solid var(--jg-border); overflow-wrap: anywhere; }
@media (max-width: 600px) { .trip-navigator { padding: 14px; } header { align-items: stretch; flex-direction: column; } h3 { font-size: 20px; } }
</style>
