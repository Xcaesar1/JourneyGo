// Offline registry regression against local or authenticated staging assets.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const live = process.argv.includes('--live');
  const auth = live ? JSON.parse(fs.readFileSync(process.env.TRAVEL_UI_AUTH_FILE, 'utf8')) : null;
  const base = auth?.url || process.env.TRAVEL_UI_URL || 'http://127.0.0.1:5173';
  const data = JSON.parse(fs.readFileSync('backend/app/domain/data/flight_cities.json', 'utf8'));
  const codes = Object.fromEntries(Object.entries(data.cities).map(([name, row]) => [name, row.code]));
  for (const [alias, name] of Object.entries(data.aliases)) codes[alias] = codes[name];
  const fixture = JSON.parse(fs.readFileSync('tests/fixtures/legacy/trip_status_completed.json', 'utf8')).result.data;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, ...(auth ? { httpCredentials: { username: auth.username, password: auth.password } } : {}) });
    const errors = []; let posts = 0;
    page.on('pageerror', e => errors.push(e.message));
    if (live) {
      const response = await page.request.get(new URL('/api/v2/travel/capabilities', base).href);
      assert.equal(response.status(), 200);
      assert.deepEqual((await response.json()).flight.city_codes, codes);
    }
    await page.route('**/api/**', route => {
      if (route.request().method() === 'POST') posts++;
      const path = new URL(route.request().url()).pathname;
      return route.fulfill({ json: path.endsWith('/capabilities')
        ? { train: { enabled: true }, hotel: { enabled: true }, flight: { enabled: true, paid: true, city_codes: codes } }
        : { success: true, data: {}, items: [] } });
    });
    await page.goto(base);
    for (const [origin, destination, from, to] of [
      ['深圳市', '武汉市', 'SZX', 'WUH'], ['芒市', '香格里拉', 'LUM', 'DIG'],
      ['北京', '成都', 'BJS', 'CTU'], ['杭州', '乌鲁木齐', 'HGH', 'URC'],
    ]) {
      const plan = { ...fixture, origin, city: destination, travel_summary: undefined,
        days: fixture.days.map(day => ({ ...day, city: destination })) };
      await page.evaluate(plan => { sessionStorage.clear(); sessionStorage.setItem('tripPlan', JSON.stringify(plan)); localStorage.setItem('tripstar-locale', 'zh-CN'); }, plan);
      await page.goto(new URL('/result', base).href);
      const panel = page.locator('.travel-search');
      await panel.getByRole('button', { name: '飞机航班', exact: true }).click();
      assert.equal(await panel.getByLabel('出发城市三字码').inputValue(), from);
      assert.equal(await panel.getByLabel('到达城市三字码').inputValue(), to);
      assert.ok(await panel.getByRole('button', { name: '查询飞机航班', exact: true }).isDisabled());
      assert.ok(await panel.locator('#flight-city-codes option').count() >= 250);
    }
    await page.setViewportSize({ width: 390, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert.equal(posts, 0); assert.deepEqual(errors, []);
    console.log('PASS shared city registry, Shenzhen/Wuhan, exact Mangshi, aliases, multi-airport cities and consent; zero paid calls');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
