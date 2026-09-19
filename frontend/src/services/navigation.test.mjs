import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

const source = readFileSync(new URL('./navigation.ts', import.meta.url), 'utf8')
const exports = {}
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText,
  { exports, URLSearchParams })
const { amapUrl, canRoute, dayStops, progressKey, parseProgress } = exports

test('saved transfer rows expose the correct departure, arrival and return endpoints', () => {
  const code = readFileSync(new URL('./transferDetails.ts', import.meta.url), 'utf8')
  const module = { exports: {} }
  vm.runInNewContext(ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, module)
  const fn = module.exports.transferDetails
  const summary = { planning_request: { origin: '深圳' }, outbound: { origin_location: { name: '深圳北站' }, location: { name: '上海虹桥站' } }, return: { location: { name: '上海南站' } }, hotel: { name: '酒店' } }
  assert.equal(fn({ title: '出发城市内接驳（估算）' }, summary).place.name, '深圳北站')
  assert.equal(fn({ title: '到站后接驳至酒店（估算）' }, summary).from.name, '上海虹桥站')
  assert.equal(fn({ title: '酒店至返程枢纽（估算）' }, summary).place.name, '上海南站')
  assert.equal(fn({ title: '任意旧项目' }, summary), null)
  assert.equal(fn({ title: '到站后接驳至酒店' }, null), null)
})
const place = { name: '城墙 & 南门,入口', address: '西安', poi_id: 'B001ABC', location: { longitude: 108.94, latitude: 34.25 } }
const meal = { name: '餐厅', type: 'lunch', location: { longitude: 108.95, latitude: 34.26 } }
const day = { date: '2026-09-16', day_index: 0, attractions: [place], meals: [meal], timeline: [
  { item_id: 'lunch', item_type: 'meal', reference_name: meal.name, start: '2026-09-16T12:00:00' },
  { item_id: 'transport', item_type: 'transport', title: 'transfer' },
  { item_id: 'wall', item_type: 'attraction', reference_name: place.name, start: '2026-09-16T13:00:00' },
] }

test('walking, transit and driving pass the destination without a fixed current-location origin', () => {
  for (const mode of ['walk', 'bus', 'car']) {
    const url = new URL(amapUrl(place, '西安', mode))
    assert.equal(url.pathname, '/navigation')
    assert.equal(url.searchParams.get('mode'), mode)
    assert.equal(url.searchParams.get('to'), '108.94,34.25,城墙 & 南门 入口')
    assert.equal(url.searchParams.get('coordinate'), 'gaode')
    assert.equal(url.searchParams.get('callnative'), '1')
    assert.equal(url.searchParams.has('from'), false)
    assert.equal(url.searchParams.has('via'), false)
  }
})

test('driving fallback links preserve saved direction and never imply a vehicle booking', () => {
  const code = readFileSync(new URL('./transferDetails.ts', import.meta.url), 'utf8')
  const module = { exports: {} }
  vm.runInNewContext(ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, module)
  const hotel = { ...place, name: '酒店', location: { longitude: 100.1, latitude: 26.8 } }
  const item = { item_type: 'transport', route_estimate_id: 'return' }
  const routes = [{ estimate_id: 'return', origin: place.name, destination: hotel.name, mode: 'driving', provider: 'amap-driving', status: 'estimated', detail: '费用未评估' }]
  const segment = module.exports.drivingTransfers(item, day, routes, { hotel })[0]
  const url = new URL(amapUrl(segment.place, '丽江', 'car', true, segment.from))
  assert.equal(url.searchParams.get('mode'), 'car')
  assert.equal(url.searchParams.get('to'), '100.1,26.8,酒店')
  assert.ok(url.searchParams.get('from').startsWith('108.94,34.25,'))
  assert.equal(segment.detail, '费用未评估')
  assert.equal(module.exports.drivingTransfers(item, day, [{ ...routes[0], status: 'unavailable' }], { hotel }).length, 0)
  assert.equal(module.exports.drivingTransfers(item, day, routes).length, 0)
  const component = readFileSync(new URL('../components/PlaceNavigation.vue', import.meta.url), 'utf8')
  assert.ok(component.includes("amapUrl(place, city, 'car', true, from)"))
  assert.ok(component.includes("amapUrl(place, city, 'car', false, from)"))
})

test('fixed segment and explicit web fallback preserve mode and coordinates', () => {
  const url = new URL(amapUrl(place, '西安', 'bus', false, { ...place, name: '起点' }))
  assert.equal(url.searchParams.get('from'), '108.94,34.25,起点')
  assert.equal(url.searchParams.get('callnative'), '0')
  assert.equal(url.searchParams.get('mode'), 'bus')
})

test('airport driving links resolve both endpoints on arrival and return days', () => {
  const module = { exports: {} }
  vm.runInNewContext(ts.transpileModule(readFileSync(new URL('./transferDetails.ts', import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, module)
  const airport = { ...place, name: '机场' }
  const hotel = { ...place, name: '酒店', location: { longitude: 104.1, latitude: 30.6 } }
  const summary = { hotel, outbound: { location: airport }, return: { location: airport } }
  for (const [from, to] of [[airport, hotel], [hotel, airport]]) {
    const route = { estimate_id: 'airport', origin: from.name, destination: to.name, mode: 'driving', provider: 'amap-driving' }
    const segment = module.exports.drivingTransfers({ item_type: 'transport', route_estimate_id: 'airport' }, { attractions: [], meals: [] }, [route], summary)[0]
    assert.equal(segment.from.name, from.name)
    assert.equal(segment.place.name, to.name)
  }
  assert.match(module.exports.transferDetails({ title: '酒店至返程枢纽（驾车，费用未评估）' }, summary).title, /驾车，费用未评估/)
})

test('unknown providers, missing and invalid coordinates use scoped search', () => {
  for (const p of [meal, { ...place, poi_id: 'google-id' }, { ...place, location: undefined },
    { ...place, location: { longitude: 0, latitude: 0 } },
    { ...place, location: { longitude: NaN, latitude: 34 } },
    { ...place, location: { longitude: 181, latitude: 34 } }]) {
    assert.equal(canRoute(p), false)
    const url = new URL(amapUrl(p, '西安', 'walk'))
    assert.equal(url.pathname, '/search')
    assert.equal(url.searchParams.get('city'), '西安')
    assert.ok(url.searchParams.get('keyword').includes(p.name))
  }
})

test('stops use timeline order, exclude transport, preserve POI, and append hotel', () => {
  const stops = dayStops({ ...day, hotel: { name: '酒店' } })
  assert.equal(stops.length, 3)
  assert.equal(stops[0].name, meal.name)
  assert.equal(stops[1].poi_id, place.poi_id)
  assert.equal(stops[1].time, '13:00')
  assert.equal(stops[2].id, 'hotel')
  assert.equal(dayStops({ ...day, timeline: [] })[0].name, place.name)
  assert.equal(dayStops({ ...day, timeline: [], attractions: [], meals: [] }).length, 0)
})

test('progress is isolated by plan, day, coordinates, and itinerary order', () => {
  const key = progressKey('plan1', day)
  assert.notEqual(key, progressKey('plan2', day))
  assert.notEqual(key, progressKey('plan1', { ...day, date: '2026-09-17' }))
  assert.notEqual(key, progressKey('plan1', { ...day, timeline: [...day.timeline].reverse() }))
  assert.notEqual(key, progressKey('plan1', { ...day, attractions: [{ ...place, location: { longitude: 109, latitude: 34 } }] }))
})

test('progress restores only known stops and statuses, tolerating corrupt storage', () => {
  const stops = dayStops(day)
  assert.equal(JSON.stringify(parseProgress('{broken', stops)), '{}')
  assert.equal(JSON.stringify(parseProgress('null', stops)), '{}')
  assert.equal(JSON.stringify(parseProgress('[1,2]', stops)), '{}')
  const restored = parseProgress(JSON.stringify({ 'timeline:lunch': 'done', 'timeline:wall': 'skipped', stale: 'done' }), stops)
  assert.equal(restored['timeline:lunch'], 'done')
  assert.equal(restored['timeline:wall'], 'skipped')
  assert.equal(restored.stale, undefined)
  assert.equal(JSON.stringify(parseProgress('{"timeline:lunch":"arrived-automatically"}', stops)), '{}')
})
