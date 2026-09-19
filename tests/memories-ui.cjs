// Production-build browser regression with synthetic history and mocked APIs only.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const base = process.env.MEMORIES_UI_URL || 'http://127.0.0.1:5174';
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-proxy-server'] });
  try {
    const access = process.env.MEMORIES_UI_AUTH_FILE ? JSON.parse(fs.readFileSync(process.env.MEMORIES_UI_AUTH_FILE, 'utf8')) : null;
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, ...(access ? { httpCredentials: { username: access.username, password: access.password } } : {}) });
    page.setDefaultNavigationTimeout(60000);
    const errors = [];
    const historyCalls = [];
    const taskCalls = [];
    const writes = [];
    let count = 50;
    let fail = false;
    let delay = 0;
    const fixture = JSON.parse(fs.readFileSync('tests/fixtures/legacy/trip_status_completed.json', 'utf8'));
    const makeItems = () => Array.from({ length: count }, (_, i) => ({
      plan_id: `memory-${i}`, city: i === 0 ? '上海 · 苏州 · 杭州 Long destination name' : `上海 ${i}`,
      start_date: '2026-10-01', end_date: '2026-10-03', travel_days: 3,
      updated_at: new Date(Date.UTC(2026, 8, 17) - i * 60000).toISOString(),
      overall_suggestions: 'Enjoy the trip and revisit your memories. '.repeat(12),
    }));
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', entry => {
      if (process.env.MEMORIES_UI_DEBUG) console.log(entry.type(), entry.text());
      if (entry.text().includes('Failed to resolve component')) errors.push(entry.text());
    });
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (process.env.MEMORIES_UI_DEBUG && url.pathname.startsWith('/api/')) console.log(url.pathname);
      if (url.origin !== new URL(base).origin) return route.abort();
      if (!url.pathname.startsWith('/api/')) return route.continue();
      if (route.request().method() !== 'GET') writes.push(url.pathname);
      if (url.pathname === '/api/v2/attractions/candidates') {
        await new Promise(resolve => setTimeout(resolve, 500));
        return route.fulfill({ json: { city: '上海', total: 1, default_selected_ids: [], degraded: false, issues: [], items: [{
          poi_id: 'synthetic-poi', name: 'Bund fixture', city: '上海', address: '', category: 'Scenery', rating: null,
          recommendation_reason: 'Synthetic candidate', image: { url: '' }, matched_interests: [], is_must_visit: false,
        }] } });
      }
      if (url.pathname === '/api/trip/history') {
        historyCalls.push(url.searchParams.get('limit'));
        if (delay) await new Promise(resolve => setTimeout(resolve, delay));
        return route.fulfill({ status: fail ? 500 : 200, json: fail ? { detail: 'synthetic failure' } : { items: makeItems() } });
      }
      if (url.pathname.startsWith('/api/v2/trips/tasks/')) {
        taskCalls.push(url.pathname);
        return route.fulfill({ status: 404, json: { detail: 'fixture uses legacy restore' } });
      }
      if (url.pathname.startsWith('/api/trip/status/')) return route.fulfill({ json: fixture });
      return route.fulfill({ json: { success: true, data: [], items: [] } });
    });
    const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    await page.locator('.memories-entry').waitFor();
    assert.equal(historyCalls.length, 0);
    assert.equal(await page.locator('.history-section').count(), 0);
    assert.equal(await page.evaluate(() => performance.getEntriesByType('resource').some(r => /\/(Memories|Result)-/.test(r.name))), false);
    await page.locator('.special-textarea').fill('Preserve my itinerary draft');
    await page.locator('.city-row-name input').fill('上海');
    await page.locator('.discovery-load-btn').click();
    assert.equal(await page.locator('.memories-entry').isDisabled(), true);
    await page.locator('.candidate-card').click();
    await page.locator('.candidate-search input').fill('Bund');
    assert.equal(await page.locator('.candidate-card').getAttribute('aria-pressed'), 'true');
    await page.evaluate(() => sessionStorage.setItem('tripTaskId', 'stale-task'));
    delay = 500;
    await page.locator('.memories-entry').click();
    await page.locator('.memories-placeholder').waitFor();
    await page.locator('.memory-card').first().waitFor();
    delay = 0;
    assert.equal(await page.locator('.memory-card').count(), 50);
    assert.deepEqual(historyCalls, ['50']);
    await noOverflow();
    assert.equal(await page.getByText('Plan ID:', { exact: false }).count(), 0);
    await page.locator('.memory-card').nth(15).scrollIntoViewIfNeeded();
    const scroll = await page.evaluate(() => scrollY);
    await page.locator('.memory-card').nth(15).click();
    await page.locator('.memories-return').waitFor();
    await page.locator('.content-wrapper').waitFor();
    assert.ok(taskCalls.some(path => path.endsWith('/memory-15')));
    assert.ok(taskCalls.every(path => !path.endsWith('/stale-task')));
    await page.locator('.memories-return').click();
    await page.locator('.memory-card').first().waitFor();
    await page.waitForFunction(y => Math.abs(scrollY - y) < 4, scroll);
    assert.equal(historyCalls.length, 1, 'return uses the in-memory list');
    fail = true;
    await page.locator('.memories-heading button').click();
    await page.locator('.memories-error').waitFor();
    assert.equal(await page.locator('.memory-card').count(), 50, 'refresh failure preserves records');
    fail = false;
    await page.locator('.memories-error button').click();
    await page.locator('.memories-error').waitFor({ state: 'hidden' });
    await page.locator('.memories-home').click();
    await page.locator('.special-textarea').waitFor();
    assert.equal(await page.locator('.special-textarea').inputValue(), 'Preserve my itinerary draft');
    assert.equal(await page.locator('.city-row-name input').inputValue(), '上海');
    assert.equal(await page.locator('.candidate-card').getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('.candidate-search input').inputValue(), 'Bund');
    for (const [code, locale] of [['zh', 'zh-CN'], ['en', 'en-US'], ['ja', 'ja-JP'], ['ko', 'ko-KR']]) {
      const pack = JSON.parse(fs.readFileSync(`frontend/src/i18n/locales/${code}.json`, 'utf8'));
      await page.evaluate(locale => localStorage.setItem('journeygo-locale', locale), locale);
      for (const width of [360, 390, 1440]) {
        await page.setViewportSize({ width, height: 844 });
        await page.goto(base, { waitUntil: 'domcontentloaded' });
        await page.locator('.memories-entry').waitFor();
        assert.equal(await page.locator('.memories-entry').innerText(), pack.memories.title);
        const entry = await page.locator('.memories-entry').boundingBox();
        assert.equal(await page.locator('.memories-entry').evaluate(el => getComputedStyle(el).borderRadius), '0px');
        const language = await page.locator('.landing-lang-item').boundingBox();
        assert.ok(entry && entry.height >= 44 && entry.x >= 0 && entry.x + entry.width <= language.x);
        await noOverflow();
        await page.locator('.memories-entry').click();
        await page.locator('.memory-card').first().waitFor();
        await noOverflow();
        assert.equal(await page.locator('h1').innerText(), pack.memories.title);
        const columns = await page.locator('.memories-list').evaluate(el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
        assert.equal(columns, width > 640 ? 2 : 1);
        if (code === 'zh' && width !== 360) {
          await page.screenshot({ path: `artifacts/memories-${width}.png` });
        }
      }
    }
    await page.setViewportSize({ width: 390, height: 844 });
    count = 0;
    await page.goto(`${base}/history`, { waitUntil: 'domcontentloaded' });
    await page.locator('.memories-empty').waitFor();
    assert.equal(await page.locator('.memory-card').count(), 0);
    fail = true;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.locator('.memories-error').waitFor();
    assert.equal(await page.locator('.memories-empty').count(), 0);
    fail = false;
    count = 1;
    await page.locator('.memories-error button').click();
    await page.locator('.memory-card').waitFor();
    assert.equal(await page.locator('.memory-card').count(), 1);
    await page.locator('.memory-card').click();
    await page.locator('.content-wrapper').waitFor();
    await page.goBack();
    await page.locator('.memory-card').waitFor();
    assert.equal(await page.locator('.memory-card').count(), 1);
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    console.log('PASS: memories navigation, 4 languages x 3 widths, lazy loading, 0/1/50 records, loading/errors/retry, draft restore, correct plan and scroll restore');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
