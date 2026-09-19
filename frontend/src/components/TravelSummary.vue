<template>
  <section class="trip-logistics">
    <p>{{ t('oneClick.notBooked') }}</p>
    <p v-if="limitedSightseeing" class="planning-notice" role="note">{{ locale.startsWith('zh') ? '往返交通占比较高，主要可游览日期：' : 'Travel takes a substantial part of this trip. Main sightseeing dates: ' }}{{ sightseeingDates }}{{ locale.startsWith('zh') ? '。抵达和返程当天按剩余时间安排，不代表完整游览日。' : '. Arrival and departure days use only the remaining time.' }}</p>
    <p v-for="notice in summary.planning_notices || []" :key="notice" class="planning-notice" role="note">{{ notice }}</p>
    <p v-for="window in windows.filter((item: any) => item.sightseeing_note)" :key="window.date" class="planning-notice" role="note">{{ window.sightseeing_note }}</p>
    <details v-if="summary.landmark_coverage?.length || summary.deduplicated_places?.length" class="planning-notice">
      <summary>{{ locale.startsWith('zh') ? '代表景点与去重说明' : 'Landmarks and duplicate experiences' }}</summary>
      <p v-for="item in summary.landmark_coverage || []" :key="item.name">{{ item.name }} · {{ item.status === 'scheduled' ? (locale.startsWith('zh') ? '已安排，时长为规划估算' : 'Scheduled; estimated visit time') : item.reason }} <a v-if="item.identity_source" :href="item.identity_source" target="_blank" rel="noopener noreferrer">{{ locale.startsWith('zh') ? '景点资料' : 'Source' }}</a></p>
      <p v-for="item in summary.deduplicated_places || []" :key="item.removed">{{ item.removed }} → {{ locale.startsWith('zh') ? '同类体验只保留' : 'Same experience; retained' }} {{ item.kept }}</p>
    </details>
    <div class="logistics-grid">
      <article v-for="direction in ['outbound', 'return']" :key="direction">
        <h3>{{ t(direction === 'outbound' ? 'oneClick.outbound' : 'oneClick.inbound') }} · <span class="train-number">{{ summary[direction].number }}</span></h3>
        <p>{{ summary[direction].from_name }} → {{ summary[direction].to_name }}</p>
        <p>{{ summary[direction].departure.replace('T', ' ') }} → {{ summary[direction].arrival.replace('T', ' ') }}</p>
        <p>{{ summary[direction].seat }} · CNY {{ money(summary[direction].price_cents) }} / {{ t('travelUnits.perPerson') }} × {{ summary.planning_request.travelers }}</p>
        <a :href="amapUrl(summary[direction].location, city, 'bus')" target="_blank" rel="noopener noreferrer">{{ summary[direction].location.name }} · AMap</a>
        <button type="button" :disabled="busy" @click="open(summary[direction].provider)">{{ t('oneClick.replace') }}</button>
      </article>
      <article>
        <h3>{{ t('oneClick.hotel') }} · {{ summary.hotel.name }}</h3>
        <HotelPhoto :hotel="summary.hotel" :city="city" />
        <p>{{ summary.hotel.room_name }} · {{ summary.hotel.check_in }} → {{ summary.hotel.check_out }}</p>
        <p>{{ t('travelUnits.stay', { rooms: summary.hotel.rooms || 1, nights: summary.hotel.nights || summary.planning_request.travel_days - 1, adults: summary.planning_request.travelers }) }}</p>
        <p>CNY {{ money(summary.hotel.cost_cents) }} · {{ t('oneClick.estimated') }}</p>
        <p>{{ summary.hotel.pricing_note }}</p>
        <a :href="amapUrl(summary.hotel, city, 'bus')" target="_blank" rel="noopener noreferrer">{{ summary.hotel.address }} · AMap</a>
        <button type="button" :disabled="busy" @click="open('hotel')">{{ t('oneClick.replace') }}</button>
      </article>
      <article>
        <h3>{{ locale.startsWith('zh') ? '已统计费用' : 'Counted costs' }} · CNY {{ money(summary.expected_cents) }}</h3>
        <p v-if="summary.driving_fallback_days?.length" class="planning-notice" role="note">{{ locale.startsWith('zh') ? '驾车兜底日的市内交通费用未评估、不计入总额（不是免费），需自行确认车辆与费用：' : 'Local transport on driving-fallback days is unpriced and excluded (not free). Arrange and price vehicles separately: ' }}{{ summary.driving_fallback_days.join(' / ') }}</p>
        <p>{{ locale.startsWith('zh') ? '部分餐费未计入，实际以店内为准。' : 'Some meals are excluded; confirm prices in store.' }}</p>
        <p v-if="!summary.meal_pricing_policy">{{ locale.startsWith('zh') ? '餐费沿用历史估算，非商家报价。' : 'Meal costs are historical estimates, not restaurant quotes.' }}</p>
        <p>{{ t('oneClick.quoted') }}: {{ money(summary.known_cents) }}</p>
        <p>{{ t('oneClick.estimated') }}: {{ money(summary.estimated_cents) }}</p>
        <p>{{ t('oneClick.unknown') }}</p>
        <details><summary>{{ t('oneClick.retained') }}</summary><p v-for="(quote, i) in summary.quotes" :key="i"><a :href="quote.source_url" target="_blank" rel="noopener noreferrer">{{ quote.provider }}</a> · {{ quote.fetched_at }}</p></details>
      </article>
    </div>
    <form v-if="editing && draft" class="quote-editor" @submit.prevent="submit">
      <label>{{ t('home.originLabel') }}<input v-model="draft.origin" required maxlength="120" /></label>
      <label>{{ t('home.cityLabel') }}<input v-model="draft.destinations[0].city" required maxlength="120" /></label>
      <label>{{ t('home.transportationLabel') }}<select v-model="draft.intercity_mode"><option value="train">{{ t('oneClick.train') }}</option><option value="flight">{{ t('oneClick.flight') }}</option></select></label>
      <label>{{ t('home.startDateLabel') }}<input v-model="draft.start_date" type="date" required /></label>
      <label>{{ t('home.travelDaysLabel') }}<input v-model.number="draft.travel_days" type="number" min="2" max="29" required /></label>
      <label>{{ t('home.budgetLabel') }}<input v-model.number="draft.budget_total" type="number" min="100" required /></label>
      <label>{{ t('home.accommodationLabel') }}<select v-model="draft.hotel_tier"><option v-for="tier in ['economy','business','premium']" :key="tier" :value="tier">{{ t('oneClick.' + tier) }}</option></select></label>
      <label>{{ t('home.travelersLabel') }}<input v-model.number="draft.travelers" type="number" min="1" max="2" required /></label>
      <label v-if="draft.intercity_mode === 'flight'"><input v-model="consent" type="checkbox" required />{{ t('oneClick.flightConsent') }}</label>
      <button type="submit" :disabled="busy">{{ t('oneClick.replace') }}</button>
    </form>
  </section>
</template>

<script setup lang="ts">
import HotelPhoto from './HotelPhoto.vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import { amapUrl } from '@/services/navigation'
const props = defineProps<{ summary: Record<string, any>; city: string; busy: boolean }>()
const emit = defineEmits<{ change: [value: Record<string, any>] }>()
const { t, locale } = useI18n()
const windows = computed(() => props.summary.activity_windows || [])
const hasSightseeing = (window: any) => window.scheduled_attractions !== undefined ? window.scheduled_attractions > 0 : window.available_minutes >= 180
const limitedSightseeing = computed(() => windows.value.some((window: any) => window.is_transfer_day && !hasSightseeing(window)))
const sightseeingDates = computed(() => windows.value.filter(hasSightseeing).map((window: any) => window.date).join(' / ') || (locale.value.startsWith('zh') ? '请查看每日时间线' : 'See the daily timeline'))
const editing = ref('')
const draft = ref<Record<string, any> | null>(null)
const consent = ref(false)
watch(() => [draft.value?.start_date, draft.value?.travel_days, draft.value?.travelers, draft.value?.intercity_mode, draft.value?.origin, draft.value?.destinations[0]?.city], () => { consent.value = false })
const money = (value: number) => (value / 100).toFixed(2)
function open(provider: string) {
  editing.value = provider
  consent.value = false
  draft.value = JSON.parse(JSON.stringify(props.summary.planning_request))
}
function submit() {
  if (!draft.value || props.busy) return
  draft.value.end_date = dayjs(draft.value.start_date).add(draft.value.travel_days - 1, 'day').format('YYYY-MM-DD')
  draft.value.destinations[0].days = draft.value.travel_days
  draft.value.flight_confirmed = consent.value
  emit('change', { instruction: 'Refresh travel proposal', travel_request: draft.value,
    refresh_travel: editing.value === 'hotel' ? 'hotel' : draft.value.intercity_mode, confirm_flight_queries: consent.value,
    day_indices: [], add_attractions: [], remove_attractions: [], refresh_sources: false })
  consent.value = false
}
</script>

<style scoped>
.trip-logistics { margin: 24px 0; padding: 24px; border: 1px solid var(--jg-border); border-radius: 20px; background: var(--jg-surface); color: var(--jg-text); }
.planning-notice { padding: 12px 16px; border: 1px solid var(--jg-border); border-radius: 12px; background: var(--jg-soft); overflow-wrap: anywhere; }
.logistics-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
article { padding: 20px; background: var(--jg-bg); border-radius: 20px; overflow-wrap: anywhere; border: 1px solid var(--jg-border); }
article:last-child { background: var(--jg-soft); }
h3 { font-size: 20px; line-height: 1.5; margin: 0 0 16px; }
p { font-size: 16px; margin-bottom: 12px; }
h3, p { color: inherit; } a { color: var(--jg-accent-strong); } button { display: block; margin-top: 16px; padding: 10px 16px; border-radius: 12px; color: var(--jg-accent-strong); background: var(--jg-surface); border: 1px solid var(--jg-border); cursor: pointer; }
.quote-editor { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px; } label { display: grid; gap: 6px; } input, select { min-height: 40px; max-width: 100%; color: var(--jg-text); background: var(--jg-surface); border: 1px solid var(--jg-border); }
@media(max-width:640px) { .trip-logistics { padding: 16px; } .logistics-grid { grid-template-columns: 1fr; } .quote-editor { display: grid; min-width: 0; } .quote-editor input, .quote-editor select { width: 100%; min-width: 0; } }
</style>
