import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'
import { createI18n } from 'vue-i18n'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const packs = Object.fromEntries(['en', 'zh', 'ja', 'ko'].map(code => [code, JSON.parse(read(`./locales/${code}.json`))]))
const flatten = (object, prefix = '') => Object.fromEntries(Object.entries(object).flatMap(([key, value]) => {
  const path = prefix ? `${prefix}.${key}` : key
  return typeof value === 'string' ? [[path, value]] : Object.entries(flatten(value, path))
}))

test('all languages and visible brand entry points use JourneyGo', () => {
  for (const pack of Object.values(packs)) {
    assert.equal(pack.app.title, 'JourneyGo')
    assert.equal(pack.app.brand, 'JourneyGo')
    assert.equal(pack.app.footerBrand, 'JourneyGo')
    assert.doesNotMatch(JSON.stringify(pack), /TripStar|旅途星辰/)
  }
  assert.match(read('../views/Landing.vue'), /<NavBar/)
  assert.match(read('../components/NavBar.vue'), /\{\{ t\('app.brand'\) \}\}/)
  assert.match(read('../../index.html'), /<title>JourneyGo<\/title>/)
})

test('homepage slogans use the updated JourneyGo copy in all four languages', () => {
  const slogans = {
    zh: '即刻启程，见所未见 ！',
    en: 'Start Your Journey, Find Your Trail.',
    ja: '今すぐ旅へ、まだ見ぬ世界に出会おう！',
    ko: '지금 떠나, 아직 만나지 못한 세상을 발견하세요!',
  }
  for (const [code, slogan] of Object.entries(slogans)) assert.equal(packs[code].home.titleLine, slogan)
  assert.match(read('../views/Landing.vue'), /t\('home.hero.title'\)/)
})

test('Korean covers every existing message and preserves interpolation parameters', () => {
  const expected = flatten(packs.en)
  const actual = flatten(packs.ko)
  assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort())
  for (const [key, value] of Object.entries(actual)) {
    assert.ok(value.trim(), key)
    assert.deepEqual((value.match(/\{\w+\}/g) || []).sort(), (expected[key].match(/\{\w+\}/g) || []).sort(), key)
  }
  for (const pack of Object.values(packs)) assert.equal(pack.app.language.ko, '한국어')
})

test('README branding and favicon use the supplied JourneyGo assets', () => {
  for (const file of ['README.md', 'README_en.md', 'README_ja.md']) {
    const document = read(`../../../${file}`)
    assert.match(document, /src="docs\/assets\/journeygo-logo\.png" alt="JourneyGo"/)
    assert.doesNotMatch(document, /4bf6f5b1-b67d-4df6-9690-f99367fef473/)
  }
  const logo = readFileSync(new URL('../../../docs/assets/journeygo-logo.png', import.meta.url))
  assert.equal(logo.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
  const icon = readFileSync(new URL('../../favicon.png', import.meta.url))
  assert.equal(icon.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
  assert.match(read('../../index.html'), /rel="icon" type="image\/png" href="\/favicon\.png"/)
})

function loadLocale(browserLanguage, saved) {
  const storage = new Map(saved ? [['tripstar-locale', saved]] : [])
  const document = { documentElement: { lang: '' } }
  const config = { exports: {} }
  const transpile = source => ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
  vm.runInNewContext(transpile(read('./messages.ts')), {
    exports: config.exports,
    require: path => ({ default: packs[path.match(/\/([a-z]+)\.json$/)[1]] }),
  })
  const exports = {}
  vm.runInNewContext(transpile(read('./index.ts')), {
    exports,
    require: path => path === 'vue-i18n'
      ? { createI18n: options => createI18n(JSON.parse(JSON.stringify(options))) }
      : config.exports,
    window: { navigator: { language: browserLanguage } },
    document,
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
  })
  return { ...exports, storage, document }
}

test('Korean browser language is detected and selection survives reload', () => {
  const app = loadLocale('ko')
  assert.equal(app.getCurrentLocale(), 'ko-KR')
  assert.equal(app.document.documentElement.lang, 'ko-KR')
  assert.equal(app.i18n.global.t('common.dayNumber', { day: 2 }), '2일차')
  app.setAppLocale('en-US')
  assert.equal(app.storage.get('tripstar-locale'), 'en-US')
  app.setAppLocale('ko-KR')
  assert.equal(loadLocale('en-US', app.storage.get('tripstar-locale')).getCurrentLocale(), 'ko-KR')
})

test('all navigation menus offer only Chinese and English while retaining stored data compatibility', () => {
  assert.doesNotMatch(read('../components/NavBar.vue'), /value="(?:ko-KR|ja-JP)"/)
  assert.match(read('../components/NavBar.vue'), /showSettings: false/)
  assert.doesNotMatch(read('../components/NavBar.vue'), /\.landing-github-item\s*\{\s*display: none/)
  assert.match(read('../components/NavBar.vue'), /locale.value = 'zh-CN'/)
  assert.match(read('../views/Landing.vue'), /<NavBar limited-languages/)
  assert.match(read('../App.vue'), /<a-config-provider :locale="componentLocale">/)
  assert.match(read('../App.vue'), /'ko-KR': koKR/)
})
