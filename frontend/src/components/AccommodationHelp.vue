<template>
  <span ref="anchor" class="accommodation-help-anchor" @pointerenter="enter" @pointerleave="leave">
    <Popover :open="open" :trigger="[]" placement="bottom" :auto-adjust-overflow="true"
      overlay-class-name="accommodation-help-popup" :overlay-style="journeyVariables">
      <template #content>
        <div id="accommodation-help-content" role="note" class="accommodation-help-content">
          <strong>{{ t('home.accommodationLabel') }}</strong>
          <p v-for="tier in ['economy', 'business', 'premium']" :key="tier">
            {{ t('oneClick.' + tier) }}: {{ ranges[tier] }}
          </p>
          <p>{{ t('home.accommodationHelpNote') }}</p>
        </div>
      </template>
      <button type="button" class="accommodation-help-button" :aria-label="t('home.accommodationHelpLabel')"
        :aria-expanded="open" :aria-describedby="open ? 'accommodation-help-content' : undefined"
        @focus="open = true" @blur="open = false" @click.stop.prevent="open = true">
        <span aria-hidden="true">?</span>
      </button>
    </Popover>
  </span>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Popover } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { journeyVariables } from '@/styles/journeyTheme'

const { t } = useI18n()
const open = ref(false)
const anchor = ref<HTMLElement | null>(null)
const ranges: Record<string, string> = { economy: '0–3', business: '3–4.5', premium: '4.5–5' }
const enter = (event: PointerEvent) => { if (event.pointerType === 'mouse') open.value = true }
const leave = () => { if (!anchor.value?.contains(document.activeElement)) open.value = false }
const dismiss = (event: PointerEvent) => {
  const target = event.target as HTMLElement
  if (!anchor.value?.contains(target) && !target.closest('.accommodation-help-popup')) open.value = false
}
const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') open.value = false }
onMounted(() => {
  document.addEventListener('pointerdown', dismiss)
  document.addEventListener('keydown', escape)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', dismiss)
  document.removeEventListener('keydown', escape)
})
</script>

<style scoped>
.accommodation-help-anchor { position: relative; display: inline-block; width: 36px; height: 1em; margin-left: 4px; vertical-align: middle; }
.accommodation-help-button { position: absolute; inset: 50% auto auto 0; transform: translateY(-50%); width: 44px; height: 44px; padding: 0; border: 0; background: transparent; color: var(--jg-accent); cursor: pointer; display: grid; place-items: center; }
.accommodation-help-button span { display: grid; place-items: center; width: 21px; height: 21px; border: 1px solid currentColor; border-radius: 50%; font: 600 14px/1 sans-serif; }
.accommodation-help-button:focus-visible { outline: 2px solid var(--jg-accent); outline-offset: -3px; border-radius: 12px; }
</style>

<style>
.accommodation-help-popup { max-width: calc(100vw - 24px); }
.accommodation-help-content { width: 300px; max-width: calc(100vw - 60px); color: var(--jg-text); font-size: 16px; line-height: 1.6; }
.accommodation-help-content p { margin: 8px 0 0; }
</style>
