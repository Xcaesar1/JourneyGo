import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const landingSource = readFileSync(new URL('./Landing.vue', import.meta.url), 'utf8')

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
