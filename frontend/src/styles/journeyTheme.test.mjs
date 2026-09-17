import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const luminance = hex => {
  const rgb = hex.match(/\w\w/g).map(v => parseInt(v, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
}
test('JourneyGo primary text, secondary text, actions and semantic colors meet AA', () => {
  assert.ok((luminance('ffffff')+.05)/(luminance('087e9a')+.05) >= 4.5)
  for (const fg of ['18343e', '58717a', '06647b', '22724f', '8b590d', 'b13d42']) {
    for (const bg of ['ffffff', 'f4f8fa', 'e5f3f7']) assert.ok((luminance(bg)+.05)/(luminance(fg)+.05) >= 4.5, `${fg} on ${bg}`)
  }
})
test('theme stays below the hero and preserves real progress and human review', () => {
  const landing = read('../views/Landing.vue')
  const result = read('../views/Result.vue')
  assert.ok(landing.indexOf('<a-config-provider :theme="journeyTheme">') > landing.indexOf('journey-explore'))
  assert.doesNotMatch(landing, /formRevealStyle/)
  assert.match(landing, /loadingEvents/)
  assert.match(result, /submitTripReview\(taskId.value, \{ action: 'approve' \}\)/)
  assert.match(result, /issue.severity === 'critical'/)
  assert.doesNotMatch(result, /validationIssues.value.slice\(0, 6\)/)
  assert.doesNotMatch(result, /t\('result.execution.(validationTitle|validationEyebrow|revisionCount)'/)
  assert.match(result, /v-if="criticalValidationIssues.length > 0"/)
})
test('fonts are local, styles scoped, and reduced-motion is supported', () => {
  const css = read('./journey-theme.css')
  assert.match(css, /@fontsource-variable\/noto-sans-sc/)
  assert.doesNotMatch(css, /https?:|!important/)
  assert.match(css, /prefers-reduced-motion/)
  assert.match(css, /\.journey-theme/)
  assert.match(read('./journeyTheme.ts'), /colorBgElevated: journeyPalette.value.surface/)
})
test('outdoor text meets AA and is the sole theme in every mode', () => {
  for (const fg of ['263b30', '5d6b5c', '315b45']) {
    for (const bg of ['fffef8', 'f5f2e9', 'e5ebdf']) assert.ok((luminance(bg)+.05)/(luminance(fg)+.05) >= 4.5)
  }
  assert.ok((luminance('ffffff')+.05)/(luminance('315b45')+.05) >= 4.5)
  const theme = read('./journeyTheme.ts')
  assert.match(theme, /journeyThemeName = 'outdoor'/)
  assert.doesNotMatch(theme, /sessionStorage|clear:|setJourneyTheme/)
  assert.doesNotMatch(read('../views/Landing.vue') + read('../views/Result.vue'), /PreviewThemeSwitch/)
  const outdoor = read('./journey-outdoor.css')
  assert.match(outdoor, /lining-nums tabular-nums/)
  assert.doesNotMatch(outdoor, /\.timeline-content \{ border-left/)
  assert.doesNotMatch(theme, /fetch\(|axios|location.reload|localStorage/)
  assert.match(read('./journey-theme.css'), /@fontsource-variable\/noto-serif-sc/)
})
