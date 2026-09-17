<template>
  <div class="personal-map-export" @click.stop @keydown.stop>
    <button type="button" :disabled="busy" @click="expanded = !expanded">{{ dayIndex === undefined ? words.whole : words.day }}</button>
    <section v-if="expanded" :aria-label="words.title">
      <strong>{{ words.title }}</strong>
      <p>{{ words.consent }}</p>
      <button v-if="!result" type="button" :disabled="busy || (!reviewId && !version)" @click="submit">{{ busy ? words.loading : words.confirm }}</button>
      <p v-if="!reviewId && !version">{{ words.noVersion }}</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="result">
        <a :href="result.url" rel="noopener noreferrer">{{ words.open }}</a>
        <button type="button" @click="copy">{{ words.copy }}</button>
        <p v-if="result.omitted.length">{{ words.omitted }}{{ result.omitted.join('、') }}</p>
      </template>
      <p>{{ words.fallback }}</p>
      <p v-if="copied" role="status">{{ words.copied }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
const props = defineProps<{ taskId: string; reviewId?: string; version?: number; dayIndex?: number }>()
const { locale } = useI18n()
const words = computed(() => locale.value.startsWith('zh') ? {
  whole: '整趟地点导入高德', day: '当天地点导入高德', title: '高德 App 专属地图',
  consent: '确认后将本行程地点发送给高德，创建专属地图。打开高德后可能需要登录或定位授权。',
  confirm: '确认并创建地图', loading: '正在创建…', open: '打开高德 App', copy: '复制地图链接',
  noVersion: '请刷新以获取可导入的行程版本。', omitted: '以下地点缺少有效定位，未导入：',
  fallback: '未安装高德或无法打开？仍可使用下方单地点导航、网页版或复制地址。',
  failed: '暂时无法创建地图，请稍后重试。', copied: '链接已复制。', copyFailed: '复制失败，请长按地图链接复制。',
} : {
  whole: 'Export trip to AMap', day: 'Export day to AMap', title: 'AMap personal map',
  consent: 'Confirm to send itinerary places to AMap and create a map. AMap may request login or location permission.',
  confirm: 'Confirm and create', loading: 'Creating…', open: 'Open AMap app', copy: 'Copy map link',
  noVersion: 'Refresh to load an exportable itinerary version.', omitted: 'Locations omitted: ',
  fallback: 'No AMap app? Use individual place navigation, web maps or copy addresses below.',
  failed: 'Map creation unavailable. Please retry later.', copied: 'Link copied.', copyFailed: 'Copy failed. Long-press the map link to copy.',
})
const expanded = ref(false)
const busy = ref(false)
const error = ref('')
const copied = ref(false)
const result = ref<{ url: string; omitted: string[] } | null>(null)
let generation = 0
watch(() => [props.taskId, props.reviewId, props.version, props.dayIndex], () => {
  generation++; result.value = null; error.value = ''; copied.value = false; busy.value = false
})
async function submit() {
  if (busy.value) return
  const current = generation
  busy.value = true; error.value = ''
  try {
    const response = await api.post(`/api/v2/tasks/${encodeURIComponent(props.taskId)}/personal-map`, {
      review_id: props.reviewId || null, version: props.reviewId ? null : props.version,
      day_index: props.dayIndex ?? null, confirmed: true,
    }, { timeout: 45000 })
    if (current === generation) result.value = response.data
  } catch (e: any) {
    if (current === generation) error.value = typeof e.response?.data?.detail === 'string' ? e.response.data.detail : words.value.failed
  } finally { if (current === generation) busy.value = false }
}
async function copy() {
  try { await navigator.clipboard.writeText(result.value!.url); copied.value = true }
  catch { error.value = words.value.copyFailed }
}
</script>

<style scoped>
.personal-map-export { margin: 12px 0; max-width: 100%; font-size: 16px; }
section { margin-top: 12px; padding: 16px; border: 1px solid var(--jg-border); border-radius: 16px; background: var(--jg-surface); color: var(--jg-text); overflow-wrap: anywhere; }
button, a { display: inline-flex; align-items: center; min-height: 44px; padding: 10px 14px; margin: 4px 8px 4px 0; border: 1px solid var(--jg-border); border-radius: 12px; background: var(--jg-soft); color: var(--jg-accent-strong); font: inherit; cursor: pointer; white-space: normal; }
button:disabled { opacity: .6; cursor: wait; }
button:focus-visible, a:focus-visible { outline: 2px solid var(--jg-accent); outline-offset: 2px; }
p { margin: 10px 0; line-height: 1.6; }
</style>
