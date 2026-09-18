import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('./Result.vue', import.meta.url), 'utf8')
const overview = source.slice(source.indexOf('const overviewAttractions ='), source.indexOf('const destroyOverviewSwiper ='))
const resolver = source.slice(source.indexOf('const getAttractionImage ='), source.indexOf('const handleImageError ='))

test('desktop attraction gallery is a centered single-row carousel without dense coverflow or waves', () => {
  const card = readFileSync(new URL('../components/OverviewAttractionCard.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /effect: 'coverflow'/)
  assert.match(source, /centeredSlides: true/)
  assert.match(source, /slidesPerView: 'auto'/)
  assert.match(source, /transform: scale\(\.9\)/)
  assert.match(source, /overviewSwiper\?\.slideNext\(\)/)
  assert.match(card, /aspect-ratio: 4 \/ 3/)
  assert.doesNotMatch(card, /shape-fill/)
  assert.match(card, /@click="emit\('select-day', item.dayArrayIndex\)"/)
})

test('daily detail starts with the timeline instead of redundant summary and issue pills', () => {
  const template = source.split('</template>\n\n<script')[0]
  assert.doesNotMatch(template, /class="day-info"|class="day-validation-strip"/)
  assert.match(template, /class="day-timeline-section"/)
})

function imagesFor(attractions, cached = {}) {
  const code = ts.transpileModule(`${overview}\n${resolver}\n overviewAttractions.map(getAttractionImage)`, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText
  return vm.runInNewContext(code, {
    tripPlan: { value: { days: [{ attractions }] } },
    attractionPhotos: { value: cached },
    computed: fn => fn(),
    btoa: value => Buffer.from(value, 'binary').toString('base64'),
    unescape,
    encodeURIComponent,
  })
}

test('overview preserves stored POI photos without requiring the fallback cache', () => {
  const attractions = [
    { name: 'Terracotta Army', image_url: 'https://example.test/army.jpg' },
    { name: 'City Wall', image_url: 'https://example.test/wall.jpg' },
  ]
  assert.deepEqual(Array.from(imagesFor(attractions)), attractions.map(item => item.image_url))
  assert.match(source, /:image-src="getAttractionImage\(item\)"/)
  assert.match(source, /:src="getAttractionImage\(item\)"/)
})

test('stored photo wins over cached fallback', () => {
  assert.equal(imagesFor([{ name: 'Wall', image_url: 'stored.jpg' }], { Wall: 'cached.jpg' })[0], 'stored.jpg')
})

test('missing stored photo uses fetched fallback, then the placeholder', () => {
  assert.equal(imagesFor([{ name: 'Wall' }], { Wall: 'cached.jpg' })[0], 'cached.jpg')
  assert.match(imagesFor([{ name: 'Wall' }])[0], /^data:image\/svg\+xml;base64,/)
})

test('encyclopedia snippets use city-scoped keys, bounded text and attributed sources', async () => {
  const introSource = readFileSync(new URL('../services/attractionIntro.ts', import.meta.url), 'utf8')
  const code = ts.transpileModule(introSource.replace(/^import .*$/m, '').replace(/export /g, '') + '\nfetchAttractionIntro', {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  let calls = 0
  const fetchIntro = vm.runInNewContext(code, {
    getRuntimeApiBaseUrl: () => '', URLSearchParams, AbortSignal,
    fetch: async url => {
      calls++
      return { ok: true, json: async () => ({ data: {
        summary: url.includes('city=other') ? 'x'.repeat(31) : 'A short sourced introduction',
        source_url: 'https://zh.wikipedia.org/wiki/Example',
      } }) }
    },
  })
  assert.ok(await fetchIntro('Example', 'city'))
  assert.ok(await fetchIntro('Example', 'city'))
  assert.equal(calls, 1)
  assert.equal(await fetchIntro('Example', 'other'), null)
  assert.equal(calls, 2)
  const card = readFileSync(new URL('../components/OverviewAttractionCard.vue', import.meta.url), 'utf8')
  assert.match(card, /<AttractionIntro/)
  const component = readFileSync(new URL('../components/AttractionIntro.vue', import.meta.url), 'utf8')
  assert.match(component, /CC BY-SA 4\.0/)
  assert.match(source, /待核实\|预约\|门票\|营业时间/)
})
