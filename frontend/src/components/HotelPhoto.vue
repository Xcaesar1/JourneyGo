<template>
  <figure class="hotel-photo">
    <template v-if="url && !failed">
      <img :src="url" :alt="hotel.name" loading="lazy" referrerpolicy="no-referrer" @error="failed = true" />
      <figcaption>{{ locale.startsWith('zh') ? '酒店图片 · 来自高德，房型以供应商为准' : 'Hotel photo · AMap. Confirm the room type with the supplier.' }}</figcaption>
    </template>
    <template v-else>
      <p>{{ locale.startsWith('zh') ? '暂无已核实的酒店图片' : 'No verified hotel photo available' }}</p>
      <button v-if="hotel.poi_id && !attempted" type="button" :disabled="busy" @click="load">{{ locale.startsWith('zh') ? '查看酒店照片' : 'Load hotel photo' }}</button>
    </template>
  </figure>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
const props = defineProps<{ hotel: Record<string, any>; city: string }>()
const { locale } = useI18n()
const loaded = ref('')
const failed = ref(false)
const attempted = ref(false)
const busy = ref(false)
let generation = 0
const url = computed(() => {
  const value = loaded.value || (props.hotel.image?.source === 'amap' ? props.hotel.image.url : '')
  return typeof value === 'string' && /^https?:\/\//.test(value) ? value : ''
})
watch(() => [props.hotel.poi_id, props.hotel.name], () => { generation++; loaded.value = ''; failed.value = false; attempted.value = false; busy.value = false })
async function load() {
  if (busy.value) return
  const current = generation
  busy.value = true
  try {
    const { data } = await api.get('/api/poi/photo', { params: { name: props.hotel.name, city: props.city, poi_id: props.hotel.poi_id } })
    if (current === generation && data.data?.source === 'amap') loaded.value = data.data.image_url || data.data.photo_url || ''
  } catch { /* Keep the explicit no-photo state; never substitute another property. */ }
  finally { if (current === generation) { busy.value = false; attempted.value = true } }
}
</script>
<style scoped>
.hotel-photo { margin: 12px 0; }
img { display: block; width: 100%; max-height: 220px; object-fit: cover; border-radius: 12px; }
figcaption, p { font-size: 16px; line-height: 1.6; color: var(--jg-muted); }
button { min-height: 44px; padding: 8px 12px; border: 1px solid var(--jg-border); border-radius: 12px; background: var(--jg-soft); color: var(--jg-text); font: inherit; cursor: pointer; }
</style>
