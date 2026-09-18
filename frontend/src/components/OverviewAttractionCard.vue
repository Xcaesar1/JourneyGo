<template>
  <div class="swiper-slide" :class="{ 'swiper-slide-active': active }" @focusin="emit('focus')">
    <div class="swiper-slide-img">
      <img :src="imageSrc" :alt="item.name" loading="lazy" @error="emit('image-error', $event)" />
    </div>
    <div class="swiper-slide-content">
      <div>
        <h2>{{ item.name }}</h2>
        <AttractionIntro :name="item.name" :city="item.city || ''">
          <p>{{ locale.startsWith('zh') ? '暂无可核实的背景简介' : 'No verified background available' }}</p>
          <p>{{ item.address || item.description || t('common.noData') }}</p>
        </AttractionIntro>
        <a class="show-more" href="#" target="_self" :aria-label="t('result.side.days')" @click.prevent="emit('select-day', item.dayArrayIndex)">
          <svg fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3"></path>
          </svg>
        </a>
      </div>
    </div>
  </div>
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

defineProps<{
  item: OverviewAttractionItem
  imageSrc: string
  active: boolean
}>()

const emit = defineEmits<{
  (e: 'focus'): void
  (e: 'select-day', dayArrayIndex: number): void
  (e: 'image-error', event: Event): void
}>()

const { t, locale } = useI18n()
</script>

<style scoped lang="scss">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
body {
  background: var(--jg-surface);
}
main {
  position: relative;
  width: calc(min(90rem, 90%));
  margin: 0 auto;
  display: flex;
  align-items: center;
  min-height: 100vh;
  min-height: 100svh;
  column-gap: 3rem;
  padding-block: min(20vh, 3rem);
}
.swiper {
  width: 100%;
  padding: 1.875rem 0;
}
.swiper-slide {
  width: 10.75rem;
  min-height: 25rem;
  height: auto;
  display: flex;
  flex-direction: column;
  justify-content: end;
  align-items: self-start;
  box-shadow: 0 6px 20px rgb(30 53 43 / 8%);
  border-radius: 14px;
  background-color: var(--jg-surface);
  overflow: hidden;
  position: relative;

  &-img {
    position: relative;
    width: 100%;
    height: 18rem;
    flex-shrink: 0;
    overflow: hidden;
    line-height: 0;
    background-color: var(--jg-surface);

    img {
      width: 100%;
      height: 100%;
      position: absolute;
      inset: 0;
      object-fit: cover;
      z-index: 0;
      transition: transform 0.3s ease-in-out;
    }

  }

  &-content {
    position: relative;
    z-index: 2;
    background: var(--jg-surface);
    border-bottom-left-radius: 0.5rem;
    border-bottom-right-radius: 0.5rem;
    padding: 14px 1.65rem;
    flex: 1;
    display: flex;
    flex-direction: column;
    width: 100%;

    > div {
      // transform: translateY(-0.75rem);
    }

    h2 {
      color: var(--jg-text);
      font-weight: 700;
      font-size: 1.4rem;
      line-height: 1.4;
      margin-bottom: 0.425rem;
      text-transform: capitalize;
      letter-spacing: 0.02rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    p {
      color: var(--jg-text);
      line-height: 1.6;
      font-size: 0.9rem;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .show-more {
      width: 3.125rem;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--jg-soft);
      border-radius: 50%;
      box-shadow: var(--jg-shadow);
      margin-top: 1em;
      margin-bottom: 0.8em;
      height: 0;
      opacity: 0;
      transition: opacity 0.3s ease-in;
      margin-left: auto;

      &:hover {
        background: var(--jg-soft);
      }

      svg {
        width: 1.75rem;
        color: var(--jg-text);
      }
    }
  }
}

.swiper-slide-active:hover img {
  transform: scale(1.03);
}

.swiper-slide-active:hover .show-more {
  opacity: 1;
  height: 3.125rem;
}

.swiper-slide-active:hover p {
  display: block;
  overflow: visible;
}

.swiper-3d .swiper-slide-shadow-left,
.swiper-3d .swiper-slide-shadow-right {
  background-image: none;
}

@media screen and (min-width: 93.75rem) {
  .swiper {
    width: 85%;
  }
}

@media (max-width: 768px) {
  .swiper-slide {
    height: auto;
    justify-content: flex-start;
    background: var(--jg-surface);
    color-scheme: light;
    border-radius: 12px;
  }
  .swiper-slide-img { height: 210px; }
  .swiper-slide-content { background: var(--jg-surface); padding: 14px 16px; }
  .swiper-slide-content h2 { color: var(--jg-text); white-space: normal; font-size: 21px; overflow-wrap: anywhere; }
  .swiper-slide-content p { color: var(--jg-text); display: block; font-size: 16px; }
  .swiper-slide-content .show-more { height: 44px; width: 44px; opacity: 1; margin-top: 10px; margin-bottom: 0; }
  .swiper-slide-active:hover img { transform: none; }
}
</style>
