import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')

test('map has a definite viewport height and validates stored coordinates', () => {
  const result = read('./Result.vue')
  assert.match(result, /#amap-container\s*\{[^}]*height: clamp\(360px, 65vh, 600px\)/s)
  assert.match(result, /toRoutePoint\(attraction.location\)/)
  assert.match(result, /mapNoCoordinates/)
  assert.match(result, /if \(section !== 'map'\) destroyCurrentMap\(\)/)
  assert.match(result, /generation !== mapGeneration/)
})

test('mobile result navigation exposes all sections without a horizontal overflow menu', () => {
  const result = read('./Result.vue')
  assert.match(result, /<nav class="mobile-section-nav"/)
  for (const key of ['map', 'days', 'knowledge-graph']) {
    assert.ok(result.includes(`{ key: '${key}', label:`))
  }
  assert.match(result, /grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/)
  assert.match(result, /:aria-current="activeSection === section.key/)
  assert.match(result, /xs: 1, sm: 1, md: 2/)
})

test('phone cards do not require hover and navbar overrides legacy full-width brand row', () => {
  const card = read('../components/OverviewAttractionCard.vue').split('@media (max-width: 768px)')[1]
  assert.match(card, /height: auto/)
  assert.match(card, /white-space: normal/)
  assert.match(card, /min-height: 44px/)
  const navbar = read('../components/NavBar.vue')
  assert.match(navbar, /\.landing-navbar \.navbar-translate\s*\{[^}]*width: auto !important/s)
  assert.match(navbar, /flex-direction: row !important/)
})

test('result removes version history and source panels without removing review or attribution', () => {
  const result = read('./Result.vue')
  assert.doesNotMatch(result, /key[=:]\s*["'](?:versions|sources)["']/)
  assert.doesNotMatch(result, /id="(?:versions|sources)"/)
  assert.doesNotMatch(result, /refreshVersions|rollbackTripVersion|compareTripVersions/)
  // Reading the active version for map export must not restore the removed history UI.
  assert.match(result, /mapVersion\.value = \(await getTripVersions\(task.trip_id\)\)\.find/)
  assert.match(result, /submitTripReview/)
  assert.match(result, /currentReview\.proposed_version/)
  assert.match(result, /Weather data by Open-Meteo \(CC BY 4\.0\)/)
  assert.match(result, /<TravelSearch v-else :plan="tripPlan"/)
  assert.match(result, /<TravelSummary v-if="tripPlan.travel_summary"/)
})
