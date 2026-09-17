// All APIs and task events are synthetic. Never contact paid travel providers.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-proxy-server'] });
  const base = process.env.TRAVEL_UI_URL || 'http://127.0.0.1:5174';
  const legacy = JSON.parse(fs.readFileSync('tests/fixtures/legacy/trip_status_completed.json', 'utf8')).result.data;
  const request = { planning_mode: 'one_click', origin: '上海', destinations: [{ city: '西安', days: 5 }],
    start_date: '2026-09-20', end_date: '2026-09-24', travel_days: 5, budget_total: '10000',
    travelers: 1, intercity_mode: 'train', hotel_tier: 'business', interests: [], must_visit: [],
    free_text_input: '', daily_start_time: '09:00:00', daily_end_time: '21:00:00' };
  const poi = { name: '测试地点', address: '西安市模拟地址', poi_id: 'BTEST123', location: { longitude: 108.95, latitude: 34.26 } };
  const leg = { number: 'G123', from_name: '上海虹桥站', to_name: '西安北站', departure: '2026-09-20T08:00:00',
    arrival: '2026-09-20T14:00:00', seat: '二等座', price_cents: 66950, provider: 'train', location: poi };
  const summary = { outbound: leg, return: { ...leg, number: 'G124', departure: '2026-09-24T14:00:00', arrival: '2026-09-24T20:00:00' },
    hotel: { ...poi, name: '测试商务酒店', room_name: '商务房', check_in: '2026-09-20', check_out: '2026-09-24', cost_cents: 140000,
      pricing_note: '按参考均价乘 4 晚估算，税费待核实' }, known_cents: 133900, estimated_cents: 240000, expected_cents: 373900,
    quotes: [{ provider: 'hotel', source_url: 'https://rollinggo.store/', fetched_at: '2026-09-17T09:00:00Z' }],
    cost_items: [{ category: 'hotel', amount_cents: 140000 }, { category: 'outbound', amount_cents: 66950 }, { category: 'tickets', amount_cents: null }], planning_request: request };
  const plan = { ...legacy, origin: '上海', city: '西安', travel_summary: summary };
  try {
    for (const locale of ['zh-CN', 'en-US', 'ja-JP', 'ko-KR']) {
      const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
      const errors = [], submissions = [];
      let paused = true;
      const task = () => ({ task_id: 'fixture-task', trip_id: 'fixture-trip', trace_id: 'fixture-trace', progress: 40,
        status: paused ? 'awaiting_input' : 'completed', stage: paused ? 'query_hotel' : 'completed',
        message: '请调整酒店偏好', pending_input: paused ? { message: '请调整酒店偏好', provider: 'hotel' } : null,
        result: paused ? null : { success: true, data: plan } });
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(locale => { localStorage.setItem('tripstar-locale', locale); sessionStorage.setItem('tripTaskId', 'fixture-task'); }, locale);
      await page.route('https://api.qrserver.com/**', route => route.abort());
      await page.route('**/api/**', route => {
        const path = new URL(route.request().url()).pathname;
        let body = { success: true, data: [], items: [] };
        if (path.endsWith('/capabilities')) body = { one_click: { enabled: true }, train: { enabled: true }, hotel: { enabled: true }, flight: { enabled: true, paid: true } };
        if (path.endsWith('/fixture-task')) body = task();
        if (path.endsWith('/fixture-trip')) body = { request };
        if (path.endsWith('/travel-queries')) body = [{ provider: 'train', scope: 'outbound', status: 'succeeded', fetched_at: '2026-09-17T09:00:00Z' }];
        if (path.endsWith('/continue')) { submissions.push(route.request().postDataJSON()); paused = false; body = task(); }
        return route.fulfill({ json: body });
      });
      await page.routeWebSocket('**/ws', socket => { setTimeout(() => socket.send(JSON.stringify(task())), 30); });
      await page.goto(base);
      await page.getByText('请调整酒店偏好', { exact: true }).waitFor();
      await page.reload();
      await page.getByText('请调整酒店偏好', { exact: true }).waitFor();
      assert.ok(await page.locator('input').evaluateAll(inputs => inputs.some(input => input.value === '上海')));
      await page.locator('.submit-btn').click();
      await page.locator('.trip-logistics').waitFor({ timeout: 15000 });
      assert.equal(submissions.length, 1);
      assert.equal(submissions[0].request.planning_mode, 'one_click');
      assert.equal(submissions[0].request.end_date, '2026-09-24');
      assert.equal(submissions[0].request.hotel_tier, 'business');
      assert.equal(await page.locator('.travel-search').count(), 0);
      assert.ok(await page.locator('.trip-logistics a[href*="amap"]').count() >= 3);
      for (const width of [390, 1280]) {
        await page.setViewportSize({ width, height: 900 });
        await page.locator('.trip-logistics').scrollIntoViewIfNeeded();
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        if (locale === 'zh-CN') await page.locator('.trip-logistics').screenshot({ path: `artifacts/one-click-${width}.png`, animations: 'disabled' });
      }
      await page.locator('.trip-logistics article').nth(2).getByRole('button').click();
      assert.ok(await page.locator('.quote-editor').isVisible());
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('PASS: four locales, mobile/desktop, paused refresh restoration, continue submission, quote summary, navigation and proposal editor. All providers mocked.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
