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
  assert.match(source, /\.weather-dashboard\s*\{\s*flex-direction: column;\s*height: auto;/)
  assert.ok(source.includes('Weather data by Open-Meteo (CC BY 4.0)'))
  assert.ok(source.includes("t('result.weatherCoverage')"))
})
