import test from 'node:test'
import assert from 'node:assert/strict'
import { planningRecovery } from './planningRecovery.js'

test('model uncertainty explains cause without requiring date changes or supplier refresh', () => {
  const result = planningRecovery({ code: 'supplier_uncertain', provider: 'model' })
  assert.match(result.reason, /不代表没有车/)
  assert.deepEqual(result.actions.map(a => a.id), ['retry', 'preferences'])
})
test('budget choices never silently raise the budget', () => {
  assert.deepEqual(planningRecovery({ code: 'over_budget' }).actions.map(a => a.target), ['budget', 'hotel', 'dates'])
})
test('budget and hotel changes are explicit actionable choices', () => {
  const current = { budget: 5000, hotelTier: 'business' }
  const budget = planningRecovery({ code: 'over_budget' }, true, current).actions[0]
  assert.equal(budget.value, 6000)
  assert.match(budget.label, /6000/)
  assert.equal(current.budget, 5000)
  const hotels = planningRecovery({ code: 'no_hotel', provider: 'hotel' }, true, current).actions
  assert.deepEqual(hotels.slice(0, 2).map(a => a.value), ['economy', 'premium'])
})
test('recovery always offers two or three choices without enabling paid flights', () => {
  for (const code of ['no_transport', 'no_hotel', 'no_places', 'must_visit_unplaced', 'unknown', 'supplier_uncertain', 'flight_budget_exhausted']) {
    for (const provider of ['train', 'hotel', 'amap', 'flight', undefined]) {
      const { actions } = planningRecovery({ code, provider })
      assert.ok(actions.length >= 2 && actions.length <= 3)
      if (provider === 'flight') assert.ok(!actions.some(a => a.id === 'refresh'))
    }
  }
})
test('specific server reasons are retained and English actions are available', () => {
  const result = planningRecovery({ code: 'no_transport', message: '去程余票不足', provider: 'train' }, false)
  assert.equal(result.reason, '去程余票不足')
  assert.equal(result.actions[0].label, 'Refresh this query and continue')
})
