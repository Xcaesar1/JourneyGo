import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const landingSource = readFileSync(new URL('./Landing.vue', import.meta.url), 'utf8')

test('touch date and time pickers suppress the software keyboard only on coarse pointers', () => {
  assert.match(landingSource, /window\.matchMedia\('\(pointer: coarse\)'\)\.matches/)
  assert.equal((landingSource.match(/:input-read-only="touchPicker"/g) || []).length, 3)
})

test('starting or resuming a task brings its mounted progress panel into view', () => {
  const start = landingSource.slice(landingSource.indexOf('const startTaskUi ='), landingSource.indexOf('const taskCallbacks ='))
  assert.match(landingSource, /ref="progressRef"/)
  assert.match(start, /nextTick\(/)
  assert.match(start, /!loading.value \|\| !progress\?\.isConnected/)
  assert.match(start, /focus\(\{ preventScroll: true \}\)/)
  assert.match(start, /prefers-reduced-motion: reduce/)
  assert.match(start, /'instant' : 'smooth'/)
  assert.match(landingSource, /scroll-margin-top: 96px/)
})

test('memories are lazy and no longer fetched or rendered by the homepage', () => {
  const main = readFileSync(new URL('../main.ts', import.meta.url), 'utf8')
  const nav = readFileSync(new URL('../components/NavBar.vue', import.meta.url), 'utf8')
  assert.match(main, /component: \(\) => import\('\.\/views\/Memories.vue'\)/)
  assert.doesNotMatch(landingSource, /getTripHistory|history-section|historyPlans/)
  assert.match(landingSource, /:memories-disabled="loading \|\| discoveryLoading"/)
  assert.ok(nav.indexOf('landing-github-item') < nav.indexOf('landing-memories-item'))
  assert.ok(nav.indexOf('landing-memories-item') < nav.indexOf('landing-lang-item'))
  assert.doesNotMatch(nav, /\.nav-item:first-child/)
})

test('initial page avoids eager result imports and external font stylesheets', () => {
  const main = readFileSync(new URL('../main.ts', import.meta.url), 'utf8')
  assert.match(main, /component: \(\) => import\('\.\/views\/Result.vue'\)/)
  assert.doesNotMatch(main, /import Result from/)
  assert.doesNotMatch(main, /import Antd|app\.use\(Antd\)/)
  assert.match(main, /@fontsource\/outfit\/latin-400.css/)
  for (const path of ['../../index.html', '../App.vue', '../components/OverviewAttractionCard.vue']) {
    assert.doesNotMatch(readFileSync(new URL(path, import.meta.url), 'utf8'), /fonts\.googleapis\.com|fonts\.gstatic\.com/)
  }
})

test('hero uses the supplied landscape with accessible planning entry and no settings button', () => {
  assert.match(landingSource, /import heroImage from '@\/assets\/journeygo-hero\.png'/)
  assert.match(landingSource, /:show-settings="false" :show-cta="false"/)
  assert.match(landingSource, /class="journey-explore" :disabled="loading" @click="scrollToForm"/)
  assert.doesNotMatch(landingSource, /journey-search|heroQuery|beginExploring/)
  assert.match(landingSource, /prefers-reduced-motion: reduce/)
  assert.doesNotMatch(landingSource.split('</template>')[0], /moving-clouds|presentation-title|fog-low/)
})

test('candidate cards and search stay responsive at tablet and phone widths', () => {
  assert.match(
    landingSource,
    /@media \(max-width: 1080px\)[\s\S]*?\.candidate-grid\s*{\s*grid-template-columns:\s*repeat\(3,/,
  )
  assert.match(
    landingSource,
    /@media \(max-width: 520px\)[\s\S]*?\.candidate-grid\s*{\s*grid-template-columns:\s*repeat\(2,/,
  )
  assert.match(
    landingSource,
    /@media \(max-width: 520px\)[\s\S]*?\.candidate-search\s*{\s*width:\s*100%/,
  )
})
