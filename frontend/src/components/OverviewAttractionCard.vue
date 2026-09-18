<template>
  <article class="swiper-slide attraction-card" :class="{ 'swiper-slide-active': active }">
    <div class="attraction-photo">
      <img :src="imageSrc" :alt="item.name" loading="lazy" @error="emit('image-error', $event)" />
      <span class="day-label">{{ t('common.dayNumber', { day: item.dayArrayIndex + 1 }) }}</span>
    </div>
    <div class="attraction-copy">
      <h2>{{ item.name }}</h2>
      <AttractionIntro :name="item.name" :city="item.city || ''">
        <p class="intro-unavailable">{{ locale.startsWith('zh') ? '暂无可核实的背景简介' : 'No verified background available' }}</p>
        <p>{{ item.address || item.description || t('common.noData') }}</p>
      </AttractionIntro>
      <button class="show-more" type="button" @click="emit('select-day', item.dayArrayIndex)">
        <span>{{ locale.startsWith('zh') ? '查看当天行程' : 'View day itinerary' }}</span>
        <svg fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3" />
        </svg>
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import AttractionIntro from './AttractionIntro.vue'
type OverviewAttractionItem = {
  name: string
  city?: string
  address: string
  visit_duration: number
  description: string
  dayArrayIndex: number
}
defineProps<{ item: OverviewAttractionItem; imageSrc: string; active: boolean }>()
const emit = defineEmits<{
  (e: 'select-day', dayArrayIndex: number): void
  (e: 'image-error', event: Event): void
}>()
const { t, locale } = useI18n()
</script>

<style scoped>
.swiper-slide.attraction-card { box-sizing: border-box; display: flex; flex-direction: column; min-width: 0; height: auto; overflow: hidden; border: 1px solid var(--jg-border); border-radius: 18px; background: var(--jg-surface); box-shadow: 0 4px 18px rgb(30 53 43 / 5%); }
.attraction-photo { position: relative; aspect-ratio: 4 / 3; overflow: hidden; background: var(--jg-soft); }
.attraction-photo img { display: block; width: 100%; height: 100%; object-fit: cover; transition: transform 200ms ease; }
.day-label { position: absolute; top: 14px; left: 14px; padding: 6px 11px; border-radius: 8px; background: rgb(255 255 255 / 94%); color: #263c32; font-size: 13px; font-weight: 600; }
.attraction-copy { display: flex; flex: 1; flex-direction: column; min-width: 0; padding: 22px; }
h2 { margin: 0 0 12px; font-size: 23px; line-height: 1.4; color: var(--jg-text); white-space: normal; overflow-wrap: anywhere; }
p, .attraction-copy :deep(.attraction-intro p) { margin: 0 0 10px; font-size: 15px; line-height: 1.75; color: var(--jg-muted); }
.intro-unavailable { font-size: 13px; }
.attraction-copy :deep(.attraction-intro) { margin: 0 0 16px; }
.attraction-copy :deep(.attraction-intro p) { display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.show-more { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; min-height: 44px; margin-top: auto; padding: 14px 0 0; border: 0; border-top: 1px solid var(--jg-border); background: transparent; color: var(--jg-accent-strong); font: inherit; font-size: 14px; text-align: left; cursor: pointer; }
.show-more svg { width: 22px; height: 22px; flex-shrink: 0; }
.show-more:focus-visible { outline: 2px solid var(--jg-accent); outline-offset: 4px; border-radius: 4px; }
@media (hover: hover) and (prefers-reduced-motion: no-preference) {
  .attraction-card:hover img { transform: scale(1.025); }
}
@media (max-width: 768px) {
  .attraction-card { height: auto; }
  h2 { white-space: normal; font-size: 21px; }
  .attraction-copy { padding: 18px; }
  .show-more { min-height: 44px; }
}
</style>
