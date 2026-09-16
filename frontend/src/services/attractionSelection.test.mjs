import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildCandidateDiscoveryState,
  filterCandidateItems,
  findCandidatePageKey,
  hasCandidateImage,
  selectedCandidateNames,
  toggleCandidateSelection,
  visibleCandidateItems,
} from './attractionSelection.js'

const candidate = (poiId, name, city, overrides = {}) => ({
  poi_id: poiId,
  name,
  city,
  address: `${city}测试地址`,
  longitude: 116.3,
  latitude: 39.9,
  category: '风景名胜',
  rating: 4.8,
  image: {
    url: `https://example.test/${poiId}.jpg`,
    source: 'amap',
    author: '',
    license: '',
    source_page: '',
    attribution: '',
  },
  recommendation_score: 90,
  recommendation_reason: '热门景点',
  matched_interests: ['历史文化'],
  is_must_visit: false,
  ...overrides,
})

const page = (city, items, defaults = []) => ({
  city,
  items,
  total: items.length,
  default_selected_ids: defaults,
  degraded: false,
  issues: [],
})

test('keeps multiple cities and deduplicates valid defaults', () => {
  const beijing = page('北京', [candidate('bj-1', '故宫博物院', '北京市')], ['bj-1', 'missing'])
  const xian = page('西安', [candidate('xa-1', '西安城墙', '西安市')], ['xa-1', 'bj-1'])
  const state = buildCandidateDiscoveryState(
    [{ city: '北京', days: 2 }, { city: '西安', days: 2 }],
    [
      { status: 'fulfilled', value: beijing },
      { status: 'fulfilled', value: xian },
    ],
  )

  assert.deepEqual(Object.keys(state.pages), ['北京', '西安'])
  assert.deepEqual(state.selectedPoiIds, ['bj-1', 'xa-1'])
  assert.deepEqual(selectedCandidateNames([beijing, xian], state.selectedPoiIds), [
    '故宫博物院',
    '西安城墙',
  ])
})

test('supports searching, adding, removing, and incremental visibility', () => {
  const items = [
    candidate('hz-1', '杭州西湖风景名胜区', '杭州市'),
    candidate('hz-2', '西溪国家湿地公园', '杭州市', { category: '公园广场' }),
    candidate('hz-3', '良渚博物院', '杭州市', { category: '博物馆' }),
  ]
  const hangzhou = page('杭州', items)

  assert.deepEqual(filterCandidateItems(hangzhou, '博物馆').map(item => item.poi_id), ['hz-3'])
  assert.equal(visibleCandidateItems(hangzhou, '', 2).length, 2)
  assert.deepEqual(toggleCandidateSelection(['hz-1'], 'hz-2'), ['hz-1', 'hz-2'])
  assert.deepEqual(toggleCandidateSelection(['hz-1', 'hz-2'], 'hz-1'), ['hz-2'])
})

test('isolates a failed city without hiding successful candidates', () => {
  const beijing = page('北京', [candidate('bj-1', '天坛公园', '北京市')], ['bj-1'])
  const state = buildCandidateDiscoveryState(
    [{ city: '北京', days: 1 }, { city: '西安', days: 1 }],
    [
      { status: 'fulfilled', value: beijing },
      { status: 'rejected', reason: new Error('network unavailable') },
    ],
  )

  assert.equal(state.pages['北京'].items.length, 1)
  assert.equal(state.pages['西安'].degraded, true)
  assert.deepEqual(state.pages['西安'].issues, ['request_failed'])
  assert.deepEqual(state.selectedPoiIds, ['bj-1'])
})

test('keeps no-image candidates selectable and maps them to the requested city', () => {
  const noImage = candidate('bj-2', '北海公园', '北京市', {
    image: {
      url: '',
      source: 'placeholder',
      author: '',
      license: '',
      source_page: '',
      attribution: '',
    },
  })
  const pages = { 北京: page('北京', [noImage]) }

  assert.equal(hasCandidateImage(noImage), false)
  assert.equal(findCandidatePageKey(pages, noImage.poi_id), '北京')
  assert.deepEqual(toggleCandidateSelection([], noImage.poi_id), ['bj-2'])
})
