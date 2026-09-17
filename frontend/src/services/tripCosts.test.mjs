import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'
const exports = {}
vm.runInNewContext(ts.transpileModule(readFileSync(new URL('./tripCosts.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, { exports })
const { mealPriceText, costScope, compareCostDates } = exports
test('missing, sourced and historical meal prices stay distinct', () => {
  assert.match(mealPriceText({ estimated_cost: 0 }), /未计入/)
  assert.match(mealPriceText({ estimated_cost: 60 }), /历史估算/)
  assert.match(mealPriceText({ price_reference: { amount_cents: 4567, source: 'amap' } }), /45.67/)
})
test('date scopes include cross-month stays and whole-trip costs', () => {
  const summary = { outbound: { departure: '2026-09-30T08:00:00' }, hotel: { check_in: '2026-09-30', check_out: '2026-10-02' } }
  assert.equal(costScope('outbound', summary).scopeLabel, '2026-09-30')
  assert.match(costScope('hotel', summary).scopeLabel, /2晚/)
  assert.equal(costScope('meals', summary).scopeLabel, '全程')
  assert.equal(costScope('return', summary).scopeLabel, '待确认')
  assert.ok(compareCostDates('', '2026-09-30', true) > 0)
  assert.ok(compareCostDates('2026-10-02', '2026-09-30', true) < 0)
})
