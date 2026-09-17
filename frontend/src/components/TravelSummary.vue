<template>
  <section class="trip-logistics">
    <p>{{ t('oneClick.notBooked') }}</p>
    <div class="logistics-grid">
      <article v-for="direction in ['outbound', 'return']" :key="direction">
        <h3>{{ t(direction === 'outbound' ? 'oneClick.outbound' : 'oneClick.inbound') }} · {{ summary[direction].number }}</h3>
        <p>{{ summary[direction].from_name }} → {{ summary[direction].to_name }}</p>
        <p>{{ summary[direction].departure.replace('T', ' ') }} → {{ summary[direction].arrival.replace('T', ' ') }}</p>
        <p>{{ summary[direction].seat }} · CNY {{ money(summary[direction].price_cents) }} / {{ t('travelUnits.perPerson') }} × {{ summary.planning_request.travelers }}</p>
        <a :href="amapUrl(summary[direction].location, city, 'bus')" target="_blank" rel="noopener noreferrer">{{ summary[direction].location.name }} · AMap</a>
        <button type="button" :disabled="busy" @click="open(summary[direction].provider)">{{ t('oneClick.replace') }}</button>
      </article>
      <article>
        <h3>{{ t('oneClick.hotel') }} · {{ summary.hotel.name }}</h3>
        <p>{{ summary.hotel.room_name }} · {{ summary.hotel.check_in }} → {{ summary.hotel.check_out }}</p>
        <p>{{ t('travelUnits.stay', { rooms: summary.hotel.rooms || 1, nights: summary.hotel.nights || summary.planning_request.travel_days - 1, adults: summary.planning_request.travelers }) }}</p>
        <p>CNY {{ money(summary.hotel.cost_cents) }} · {{ t('oneClick.estimated') }}</p>
        <p>{{ summary.hotel.pricing_note }}</p>
        <a :href="amapUrl(summary.hotel, city, 'bus')" target="_blank" rel="noopener noreferrer">{{ summary.hotel.address }} · AMap</a>
        <button type="button" :disabled="busy" @click="open('hotel')">{{ t('oneClick.replace') }}</button>
      </article>
      <article>
        <h3>{{ t('oneClick.total') }} · CNY {{ money(summary.expected_cents) }}</h3>
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
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import { amapUrl } from '@/services/navigation'
const props = defineProps<{ summary: Record<string, any>; city: string; busy: boolean }>()
const emit = defineEmits<{ change: [value: Record<string, any>] }>()
const { t } = useI18n()
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
.trip-logistics { margin: 24px 0; padding: 20px; border: 1px solid #41515c; border-radius: 12px; background: #101d24; color: #ecf3fa; }
.logistics-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
article { padding: 16px; background: #15232c; border-radius: 8px; overflow-wrap: anywhere; }
h3, p { color: inherit; } a { color: #ffd5a1; } button { display: block; margin-top: 12px; padding: 10px 16px; color: white; background: #a34c2a; border: 1px solid #e79069; cursor: pointer; }
.quote-editor { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px; } label { display: grid; gap: 6px; } input, select { min-height: 40px; max-width: 100%; color: #ecf3fa; background: #15232c; border: 1px solid #41515c; }
@media(max-width:640px) { .logistics-grid { grid-template-columns: 1fr; } .quote-editor { display: grid; } }
</style>
