<template>
  <div class="place-navigation">
    <div class="navigation-actions">
      <a :href="amapUrl(place, city, 'walk')" target="_blank" rel="noopener noreferrer">{{ t(canRoute(place) ? 'navigation.walk' : 'navigation.search') }}</a>
      <a v-if="canRoute(place)" :href="amapUrl(place, city, 'bus')" target="_blank" rel="noopener noreferrer">{{ t('navigation.bus') }}</a>
      <button type="button" @click="expanded = !expanded" :aria-expanded="expanded">{{ t('navigation.more') }}</button>
    </div>
    <div v-if="expanded" class="navigation-help">
      <p>{{ t(canRoute(place) ? 'navigation.confirm' : 'navigation.unknown') }}</p>
      <template v-if="from && canRoute(from) && canRoute(place)">
        <p>{{ t('navigation.segment', { name: from.name }) }}</p>
        <a :href="amapUrl(place, city, 'walk', true, from)" target="_blank" rel="noopener noreferrer">{{ t('navigation.walk') }}</a>
        <a :href="amapUrl(place, city, 'bus', true, from)" target="_blank" rel="noopener noreferrer">{{ t('navigation.bus') }}</a>
      </template>
      <p>{{ t('navigation.fallback') }}</p>
      <a :href="amapUrl(place, city, 'walk', false)" target="_blank" rel="noopener noreferrer">{{ t('navigation.webWalk') }}</a>
      <a v-if="canRoute(place)" :href="amapUrl(place, city, 'bus', false)" target="_blank" rel="noopener noreferrer">{{ t('navigation.webBus') }}</a>
      <button type="button" @click="copyAddress">{{ t('navigation.copy') }}</button>
      <p role="status">{{ feedback }}</p>
      <input v-if="copyFailed" readonly :value="addressText" :aria-label="t('navigation.copy')" @focus="($event.target as HTMLInputElement).select()" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { amapUrl, canRoute, type NavigationPlace } from '@/services/navigation'
const props = defineProps<{ place: NavigationPlace; city: string; from?: NavigationPlace }>()
const { t } = useI18n()
const expanded = ref(false)
const feedback = ref('')
const copyFailed = ref(false)
const addressText = computed(() => [props.city, props.place.name, props.place.address].filter(Boolean).join(' '))
async function copyAddress() {
  try {
    await navigator.clipboard.writeText(addressText.value)
    feedback.value = t('navigation.copied')
    copyFailed.value = false
  } catch {
    feedback.value = t('navigation.copyFailed')
    copyFailed.value = true
  }
}
</script>

<style scoped>
.place-navigation { margin-top: 12px; }
.navigation-actions { display: flex; flex-wrap: wrap; gap: 8px; }
a, button { display: inline-flex; align-items: center; min-height: 44px; padding: 8px 12px; border: 1px solid var(--jg-border); border-radius: 8px; background: transparent; color: inherit; font: inherit; cursor: pointer; text-decoration: none; }
a:hover, button:hover { background: var(--jg-surface); }
a:focus-visible, button:focus-visible { outline: 2px solid #df9766; outline-offset: 2px; }
.navigation-help { margin-top: 8px; padding: 12px; border-left: 2px solid var(--jg-border); }
.navigation-help a, .navigation-help button { margin: 4px; }
.navigation-help p { margin: 8px 0; font-size: 16px; }
input { width: 100%; color: inherit; background: transparent; }
</style>
