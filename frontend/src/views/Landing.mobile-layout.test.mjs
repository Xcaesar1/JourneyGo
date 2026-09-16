import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const landingSource = readFileSync(new URL('./Landing.vue', import.meta.url), 'utf8')

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
