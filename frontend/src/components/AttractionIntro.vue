<template>
  <div v-if="intro" class="attraction-intro">
    <p>{{ intro.summary }}</p>
    <small>
      <a :href="intro.source_url" target="_blank" rel="noopener noreferrer">{{ locale.startsWith('zh') ? '维基百科 · 节选' : 'Wikipedia · excerpt' }}</a>
      · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a>
    </small>
    <slot name="notice" />
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { fetchAttractionIntro, type AttractionIntroData } from '@/services/attractionIntro'

const props = defineProps<{ name: string; city: string }>()
const { locale } = useI18n()
const intro = ref<AttractionIntroData | null>(null)
watch(() => [props.name, props.city], async ([name, city], _, onCleanup) => {
  let active = true
  onCleanup(() => { active = false })
  intro.value = null
  const result = await fetchAttractionIntro(name!, city!)
  if (active) intro.value = result
}, { immediate: true })
</script>

<style scoped>
.attraction-intro { margin: 12px 0; }
.attraction-intro p { font-size: 16px; line-height: 1.7; margin: 0 0 6px; }
.attraction-intro small { display: block; font-size: 12px; line-height: 1.6; }
.attraction-intro a { color: inherit; text-decoration: underline; text-underline-offset: 3px; }
</style>
