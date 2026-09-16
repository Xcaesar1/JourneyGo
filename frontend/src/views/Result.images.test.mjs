import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('./Result.vue', import.meta.url), 'utf8')
const overview = source.slice(source.indexOf('const overviewAttractions ='), source.indexOf('const destroyOverviewSwiper ='))
const resolver = source.slice(source.indexOf('const getAttractionImage ='), source.indexOf('const handleImageError ='))

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
