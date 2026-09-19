import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('./Result.vue', import.meta.url), 'utf8')
const helper = source.slice(source.indexOf('const formatWeatherPercent'), source.indexOf('const getWeatherWind'))
const format = vm.runInNewContext(ts.transpile(`${helper}\nformatWeatherPercent;`))

test('weather percentages preserve zero and never invent missing measurements', () => {
  assert.equal(format(0), '0%')
  assert.equal(format(56), '56%')
  for (const value of [null, undefined, NaN, -1, 101, '65']) assert.equal(format(value), '--')
  assert.ok(!source.includes('getWeatherHumidity'))
  assert.ok(!source.includes('getWeatherPrecipitation'))
})

test('mobile weather grows to fit measurements and attribution', () => {
  assert.match(source, /\.weather-dashboard\s*\{\s*display: flex;\s*min-height: 350px;\s*height: auto;/)
  assert.match(source, /\.weather-dashboard\s*\{\s*flex-direction: column;\s*height: auto;/)
  assert.ok(source.includes('Weather data by Open-Meteo (CC BY 4.0)'))
  assert.equal(source.split('Weather data by Open-Meteo (CC BY 4.0)').length - 1, 2)
  assert.ok(!source.includes("t('result.weatherCoverage')"))
})
test('missing trip-date forecasts have an explicit empty state without invented measurements', () => {
  assert.match(source, /v-if="!selectedWeather" class="weather-empty"/)
  assert.match(source, /result.weatherUnavailableDetail/)
  assert.match(source, /weatherMissingDates/)
  assert.match(source, /item.date === day.date/)
})

test('weather date and hero occupy separate flow blocks instead of overlapping anchors', () => {
  assert.match(source, /\.weather-side\s*\{[^}]*display: flex;[^}]*flex-direction: column;[^}]*gap: 24px;/)
  for (const selector of ['date-container', 'weather-container']) {
    const rule = source.match(new RegExp(`\\.${selector}\\s*\\{([^}]+)`))[1]
    assert.match(rule, /position: relative/)
    assert.doesNotMatch(rule, /position: absolute/)
  }
})

test('overview omits internal diagnostics while retaining the cost boundary', () => {
  const summary = readFileSync(new URL('../components/TravelSummary.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /Plan ID:/)
  assert.doesNotMatch(summary, /oneClick\.(retained|notBooked)|planning_notices|sightseeing_note|landmark_coverage|deduplicated_places/)
  assert.match(summary, /驾车日市内交通费另计/)
  assert.match(summary, /oneClick\.unknown/)
})

const weatherModule = { exports: {} }
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('../services/weatherText.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, weatherModule)
const { weatherText } = weatherModule.exports

test('weather descriptions follow all supported UI languages, including retained provider text', () => {
  assert.equal(weatherText('light drizzle', 'zh-CN'), '小毛毛雨')
  assert.equal(weatherText(' LIGHT_DRIZZLE ', 'en-US'), 'Light drizzle')
  assert.equal(weatherText('Light drizzle', 'ja-JP'), '弱い霧雨')
  assert.equal(weatherText('Light drizzle', 'ko-KR'), '약한 이슬비')
  assert.equal(weatherText('雷阵雨', 'en-US'), 'Thunderstorm')
  assert.equal(weatherText('Thunderstorm with slight hail', 'zh-CN'), '雷阵雨伴小冰雹')
  assert.equal(weatherText('', 'zh-CN'), '--')
  assert.equal(weatherText('unexpected provider description', 'zh-CN'), '暂无描述')
  assert.equal(source.match(/weatherText\(/g).length, 5, 'hero, day/night details and day/night export')
})
