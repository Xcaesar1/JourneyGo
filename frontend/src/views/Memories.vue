<template>
  <div class="memories-page">
    <NavBar :show-settings="false" :show-cta="false" @brand-click="router.push('/')" />
    <main class="memories-main">
      <router-link class="memories-home" to="/">{{ t('memories.backHome') }}</router-link>
      <header class="memories-heading">
        <div>
          <h1>{{ t('memories.title') }}</h1>
          <p>{{ t('memories.description') }}</p>
        </div>
        <button class="memories-action" :disabled="loading" @click="loadPlans">{{ t('home.history.refresh') }}</button>
      </header>
      <p v-if="error" class="memories-error" role="alert">
        {{ t('home.history.loadFailed') }}
        <button class="memories-action" :disabled="loading" @click="loadPlans">{{ t('memories.retry') }}</button>
      </p>
      <div v-if="loading && items === null" class="memories-placeholder" role="status">
        {{ t('common.loading') }}
      </div>
      <section v-else-if="items?.length === 0 && !error" class="memories-empty">
        <p>{{ t('home.history.empty') }}</p>
        <router-link class="memories-action" to="/">{{ t('memories.create') }}</router-link>
      </section>
      <div v-if="items?.length" class="memories-list" :aria-busy="loading">
        <button v-for="item in items" :key="item.plan_id" type="button" class="memory-card" @click="openPlan(item.plan_id)">
          <span class="memory-city">{{ item.city }}</span>
          <span class="memory-date">{{ item.start_date }} {{ t('common.to') }} {{ item.end_date }}</span>
          <span class="memory-meta">{{ item.travel_days }}{{ t('home.travelDaysUnit') }} · {{ t('home.history.updatedAt') }} {{ formatTime(item.updated_at) }}</span>
          <span v-if="item.overall_suggestions" class="memory-summary">{{ item.overall_suggestions }}</span>
          <span class="memory-open">{{ t('home.history.open') }} <span aria-hidden="true">&rarr;</span></span>
        </button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import NavBar from '@/components/NavBar.vue'
import { getTripHistory } from '@/services/api'
import { memoriesState } from '@/services/memoriesState'

const router = useRouter()
const { t, locale } = useI18n()
const items = ref(memoriesState.items)
const loading = ref(false)
const error = ref(false)
let active = true

const formatTime = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString(locale.value)
}

const loadPlans = async () => {
  if (loading.value) return
  loading.value = true
  error.value = false
  try {
    const result = await getTripHistory(50)
    if (!active) return
    items.value = result
    memoriesState.items = result
  } catch {
    if (active) error.value = true
  } finally {
    loading.value = false
  }
}

const openPlan = (planId: string) => {
  if (!planId) return
  // Drop the previous result's task/review too, so it cannot override this plan.
  for (const key of ['tripPlan', 'graphData', 'tripTaskId', 'tripId', 'tripReview']) sessionStorage.removeItem(key)
  sessionStorage.setItem('planId', planId)
  void router.push({ path: '/result', query: { plan_id: planId, task_id: planId, from: 'memories' } })
}

onMounted(async () => {
  if (items.value === null) await loadPlans()
  await nextTick()
  if (active) window.scrollTo({ top: memoriesState.scrollY, behavior: 'instant' })
})

onBeforeRouteLeave(() => {
  memoriesState.scrollY = window.scrollY
  active = false
})
</script>

<style scoped>
.memories-page { min-height: 100vh; color: #ecf3fa; background: radial-gradient(ellipse at 90% 0, #243d46 0, transparent 55%), linear-gradient(160deg, #142430, #0d171d); }
.memories-main { max-width: 1120px; margin: 0 auto; padding: 104px 24px 64px; }
.memories-home { display: inline-flex; align-items: center; min-height: 44px; color: #f5cb87; }
.memories-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin: 20px 0 32px; }
.memories-heading h1 { color: #f5fbff; font-size: clamp(32px, 5vw, 48px); margin: 0 0 12px; }
.memories-heading p { color: #b3c6d3; margin: 0; }
.memories-action { display: inline-flex; justify-content: center; align-items: center; min-height: 44px; padding: 8px 16px; border: 1px solid #f5cb8755; border-radius: 24px; background: #f5cb8710; color: #f5cb87; cursor: pointer; flex-shrink: 0; }
.memories-action:disabled { opacity: .5; cursor: wait; }
.memories-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.memory-card { display: flex; flex-direction: column; align-items: flex-start; gap: 10px; min-width: 0; padding: 24px; border: 1px solid #cbe3ff26; border-radius: 20px; color: inherit; background: #0a141cbb; text-align: left; cursor: pointer; overflow-wrap: anywhere; }
.memory-card:hover { border-color: #f5cb8777; background: #182b36; }
.memory-city { font-size: 22px; font-weight: 600; color: #f5fbff; }
.memory-date { font-size: 14px; color: #d1dfe8; }
.memory-meta { font-size: 12px; color: #adc3d1; }
.memory-summary { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.65; }
.memory-open { margin-top: auto; padding-top: 12px; color: #f5cb87; }
.memories-placeholder, .memories-empty { padding: 48px 24px; text-align: center; border: 1px solid #cbe3ff26; border-radius: 20px; background: #ffffff04; }
.memories-error { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px; border-radius: 16px; background: #612e2444; color: #ffd2be; }
button:focus-visible, a:focus-visible { outline: 2px solid #f5cb87; outline-offset: 4px; }
@media (max-width: 640px) {
  .memories-main { padding: 90px 16px 40px; }
  .memories-list { grid-template-columns: minmax(0, 1fr); }
  .memories-heading { align-items: flex-start; }
  .memory-card { padding: 20px; }
}
</style>
