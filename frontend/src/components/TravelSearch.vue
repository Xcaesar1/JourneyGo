<template>
  <section class="travel-search" aria-labelledby="travel-search-title">
    <header class="travel-heading">
      <div><span class="travel-eyebrow">出行实价查询</span><h2 id="travel-search-title">交通与住宿</h2></div>
      <span class="travel-badge">按需查询 · 不自动预订</span>
    </header>
    <p class="travel-intro">与行程估算分开展示。报价只代表查询时的数据，不会自动计入行程预算。</p>
    <div class="travel-tabs" role="group" aria-label="查询类型">
      <button v-for="item in tabs" :key="item.key" type="button" :aria-pressed="provider === item.key"
        :disabled="loading" @click="provider = item.key">{{ item.label }}</button>
    </div>
    <p v-if="capabilityError" role="alert">查询服务状态读取失败。<button type="button" @click="loadCapabilities">重试</button></p>
    <p v-else-if="!capabilities" role="status">正在读取查询服务状态…</p>
    <p v-else-if="!capabilities[provider].enabled" class="travel-notice" role="status">此服务尚未启用，请先由管理员配置。原行程仍可正常使用。</p>
    <form @submit.prevent="submit">
      <fieldset :disabled="loading || !capabilities?.[provider].enabled">
        <div class="travel-fields">
          <label v-if="provider !== 'hotel'">{{ provider === 'flight' ? '出发城市三字码' : '出发城市 / 车站' }}
            <input v-model.trim="form.origin" required maxlength="100" :list="provider === 'flight' ? 'flight-city-codes' : undefined"
              :placeholder="provider === 'flight' ? '例如 BJS（北京）' : '例如 北京'" :pattern="provider === 'flight' ? '[A-Z]{3}' : undefined" />
          </label>
          <label>{{ provider === 'flight' ? '到达城市三字码' : provider === 'hotel' ? '入住城市' : '到达城市 / 车站' }}
            <input v-model.trim="form.destination" required maxlength="100" :list="provider === 'flight' ? 'flight-city-codes' : 'trip-city-options'"
              :placeholder="provider === 'flight' ? '例如 SHA（上海）' : '例如 西安'" :pattern="provider === 'flight' ? '[A-Z]{3}' : undefined" />
          </label>
          <label>{{ provider === 'hotel' ? '入住日期' : '出发日期' }}
            <input v-model="form.date" type="date" required :min="today" :max="maxDate" />
          </label>
          <template v-if="provider === 'hotel'">
            <label>国家 / 地区<input v-model.trim="form.country" required maxlength="60" placeholder="例如 中国" /></label>
            <label>入住晚数<input v-model.number="form.nights" type="number" required min="1" max="28" /></label>
            <label>每间房成人数<input v-model.number="form.adults" type="number" required min="1" max="4" /></label>
          </template>
        </div>
        <datalist id="flight-city-codes"><option v-for="(code, city) in cityCodes" :key="code" :value="code">{{ city }}</option></datalist>
        <datalist id="trip-city-options"><option v-for="city in cities" :key="city" :value="city" /></datalist>
        <label v-if="provider === 'train'" class="travel-check"><input v-model="form.high_speed_only" type="checkbox" />仅高铁 / 动车（最多查询未来 15 天）</label>
        <p v-if="provider === 'hotel'" class="travel-note">当前按 1 间房、成人入住查询；暂不包含儿童和多房组合。请核对晚数，单日行程不默认代表需要住宿。</p>
        <template v-if="provider === 'flight'">
          <p class="travel-note">请使用城市三字码，而非随意选择某个机场。返回票价非含税总价，不包含已核实的行李或退改承诺。</p>
          <label class="travel-check"><input v-model="form.confirm_paid" type="checkbox" required />同意本次查询可能消耗飞常准余额；不会自动重试或购票。</label>
        </template>
        <label class="travel-access">查询访问码（航班必需；已设置可留空）<input v-model="accessCode" type="password" autocomplete="off" maxlength="256" /></label>
        <button class="travel-submit" type="submit" :disabled="provider === 'flight' && !form.confirm_paid">{{ loading ? '正在查询…' : '查询' + tabs.find(item => item.key === provider)?.label }}</button>
      </fieldset>
    </form>
    <p v-if="error" class="travel-error" role="alert">{{ error }}</p>
    <div v-if="result" class="travel-results" aria-live="polite">
      <p class="travel-result-message">{{ result.message }}<span v-if="result.cached">（5 分钟内缓存）</span></p>
      <div class="travel-offers">
        <article v-for="(offer, index) in result.offers" :key="offer.offer_id + '-' + index" class="travel-offer">
          <div class="travel-offer-heading"><h3>{{ offer.title }}</h3><strong>{{ offer.price === null ? '暂无报价' : `${offer.currency} ${offer.price}` }}</strong></div>
          <p>{{ offer.subtitle }}</p>
          <p v-if="offer.departure || offer.arrival">{{ offer.departure || '时间待核实' }} → {{ offer.arrival || '时间待核实' }}</p>
          <p class="travel-fare">{{ offer.fare_label }} · {{ offer.price_basis === 'first_night_reference' ? '首夜参考价' : offer.price_basis === 'stay_total' ? '历史住宿报价（口径待核实）' : '每人票价' }}<span v-if="offer.availability"> · 余票：{{ offer.availability }}</span></p>
          <p v-if="offer.price_basis === 'first_night_reference'">住宿参考总额：{{ offer.estimated_stay_total == null ? '待核实' : `${offer.currency} ${offer.estimated_stay_total}` }}（参考价 × 晚数，税费待核实）</p>
          <small v-for="note in offer.notes" :key="note">{{ note }}</small>
          <a v-if="offer.booking_url === 'https://www.12306.cn/'" :href="offer.booking_url" target="_blank" rel="noopener noreferrer">前往 12306 核实</a>
        </article>
      </div>
      <p v-if="result.fetched_at" class="travel-source"><a :href="result.source_url" target="_blank" rel="noopener noreferrer">来源：{{ result.source_title }}</a> · {{ new Date(result.fetched_at).toLocaleString() }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import type { TripPlan } from '@/types'
import type { TravelCapabilities, TravelProvider, TravelSearchRequest, TravelSearchResponse } from '@/types/travel'
import { getTravelCapabilities, searchTravel, setApiAccessCode } from '@/services/api'

const props = defineProps<{ plan: TripPlan }>()
const tabs: { key: TravelProvider; label: string }[] = [
  { key: 'train', label: '火车高铁' }, { key: 'hotel', label: '酒店住宿' }, { key: 'flight', label: '飞机航班' },
]
const cityCodes: Record<string, string> = { 北京: 'BJS', 上海: 'SHA', 广州: 'CAN', 合肥: 'HFE' }
const provider = ref<TravelProvider>('train')
const capabilities = ref<TravelCapabilities | null>(null)
const capabilityError = ref(false)
const loading = ref(false)
const error = ref('')
const accessCode = ref('')
const result = ref<TravelSearchResponse | null>(null)
const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
const maxDate = computed(() => {
  const date = new Date(`${today}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + (provider.value === 'train' ? 14 : 365))
  return date.toISOString().slice(0, 10)
})
const cities = computed(() => [...new Set(props.plan.days.map(day => day.city || props.plan.city))])
const form = reactive<TravelSearchRequest>({ provider: 'train', origin: '', destination: '', date: '', country: '中国', nights: 1, adults: 2, high_speed_only: true, confirm_paid: false })

function reset() {
  const origin = props.plan.origin || ''
  const destination = props.plan.days[0]?.city || props.plan.city
  form.origin = provider.value === 'flight' ? cityCodes[origin.replace(/市$/, '')] || '' : origin
  form.destination = provider.value === 'flight' ? cityCodes[destination.replace(/市$/, '')] || '' : destination
  form.date = props.plan.start_date
  form.confirm_paid = false
  result.value = null
  error.value = ''
}
watch([provider, () => props.plan], reset, { immediate: true })
watch(() => [form.origin, form.destination, form.date, form.country, form.nights, form.adults, form.high_speed_only], () => {
  result.value = null
  error.value = ''
  form.confirm_paid = false
})
async function loadCapabilities() {
  capabilityError.value = false
  try { capabilities.value = await getTravelCapabilities() }
  catch { capabilityError.value = true }
}
onMounted(loadCapabilities)

async function submit() {
  if (loading.value || !capabilities.value?.[provider.value].enabled) return
  if (provider.value === 'flight' && !form.confirm_paid) return
  loading.value = true
  error.value = ''
  result.value = null
  if (accessCode.value) {
    setApiAccessCode(accessCode.value)
    accessCode.value = ''
  }
  const request = { ...form, provider: provider.value }
  try { result.value = await searchTravel(request) }
  catch (failure: any) {
    const status = failure?.response?.status
    error.value = status === 401 ? '访问码不正确，请重新输入。'
      : status === 422 ? '请检查日期、城市及人数；高铁仅支持未来 15 天，航班需使用城市三字码。'
      : status === 429 ? '查询过于频繁，请稍后重试。'
      : '本次查询未完成，请稍后重试。未自动重试，也未创建订单。'
  } finally {
    loading.value = false
    form.confirm_paid = false
  }
}
</script>

<style scoped>
.travel-search { margin: 24px 0; padding: 24px; border: 1px solid var(--jg-border); border-radius: 16px; background: var(--jg-surface); color: var(--jg-text); color-scheme: light; }
.travel-heading, .travel-offer-heading { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; flex-wrap: wrap; }
.travel-heading h2 { margin: 4px 0; font-size: 24px; color: var(--jg-text); }
.travel-eyebrow { font-size: 16px; letter-spacing: .14em; color: var(--jg-accent-strong); }
.travel-badge { font-size: 16px; color: var(--jg-accent-strong); }
.travel-search .travel-intro, .travel-search .travel-note { color: var(--jg-text); font-size: 16px; line-height: 1.7; }
.travel-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; }
.travel-tabs button { background: var(--jg-surface); border: 1px solid var(--jg-border); border-radius: 20px; padding: 8px 18px; cursor: pointer; color: var(--jg-text); }
.travel-tabs button[aria-pressed="true"] { background: var(--jg-surface); color: var(--jg-text); border-color: var(--jg-border); }
fieldset { padding: 0; margin: 0; border: 0; min-width: 0; }
.travel-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.travel-fields label, .travel-access { display: flex; flex-direction: column; gap: 6px; font-size: 16px; }
.travel-access { max-width: 320px; }
input:not([type="checkbox"]) { min-width: 0; width: 100%; box-sizing: border-box; padding: 10px 12px; background: var(--jg-surface); border: 1px solid var(--jg-border); border-radius: 8px; color: var(--jg-text); font: inherit; }
input:focus-visible, button:focus-visible { outline: 2px solid #e79069; outline-offset: 3px; }
.travel-check { display: flex; align-items: flex-start; gap: 8px; margin: 14px 0; font-size: 16px; line-height: 1.6; }
.travel-check input { margin-top: 4px; }
.travel-submit { margin-top: 14px; border: 0; border-radius: 9px; padding: 10px 24px; background: var(--jg-surface); color: var(--jg-text); cursor: pointer; }
button:disabled, fieldset:disabled { opacity: .6; cursor: not-allowed; }
.travel-search .travel-notice { color: var(--jg-warning); background: var(--jg-surface); border-radius: 8px; padding: 12px; }
.travel-search .travel-error { color: var(--jg-text); }
.travel-results { border-top: 1px solid var(--jg-border); margin-top: 20px; padding-top: 12px; }
.travel-offers { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.travel-offer { padding: 16px; background: var(--jg-surface); border: 1px solid var(--jg-border); border-radius: 12px; overflow-wrap: anywhere; }
.travel-offer h3 { margin: 0; font-size: 16px; color: var(--jg-text); }
.travel-search .travel-offer strong { color: var(--jg-accent-strong); white-space: nowrap; }
.travel-search .travel-offer p { margin: 8px 0; font-size: 16px; color: var(--jg-text); }
.travel-offer small { display: block; color: var(--jg-text); line-height: 1.6; }
.travel-offer a, .travel-source { font-size: 16px; }
.travel-source { margin-top: 16px; color: var(--jg-text); }
.travel-search a { color: var(--jg-text); }
@media (max-width: 640px) {
  .travel-search { padding: 16px; border-radius: 14px; }
  .travel-fields, .travel-offers { grid-template-columns: 1fr; }
  .travel-submit { width: 100%; min-height: 44px; }
  .travel-tabs button { flex: 1; padding: 9px; white-space: nowrap; }
}
</style>
