// Mocked browser regression. No paid supplier call is made by this test.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.TRAVEL_UI_URL || 'http://127.0.0.1:5174';
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-proxy-server'] });
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const fixture = JSON.parse(fs.readFileSync('tests/fixtures/legacy/trip_status_completed.json', 'utf8')).result.data;
  const plan = { ...fixture, origin: '北京', city: '上海', start_date: today, end_date: today,
    days: [{ ...fixture.days[0], city: '上海', date: today }], weather_info: [] };
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    const calls = [];
    let enabled = true;
    let responseStatus = 'ok';
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      let body = { success: true, data: {} };
      if (path === '/api/v2/travel/capabilities') body = Object.fromEntries(['train', 'hotel', 'flight'].map(key => [key, { enabled, paid: key === 'flight' }]));
      if (path === '/api/v2/travel/search') {
        const request = route.request().postDataJSON();
        calls.push(request);
        body = { provider: request.provider, status: responseStatus,
          message: responseStatus === 'ok' ? '查询完成，报价及库存以预订平台为准。' : '没有符合条件的可用结果。',
          offers: responseStatus !== 'ok' ? [] : [{ offer_id: 'fixture-1', title: request.provider === 'hotel' ? '测试酒店' : '测试班次',
            subtitle: '测试路线或地址', departure: '', arrival: '', price: request.provider === 'hotel' ? 600 : 350,
            currency: 'CNY', price_basis: request.provider === 'hotel' ? 'stay_total' : 'per_person',
            fare_label: request.provider === 'hotel' ? '1 间房 · 2 位成人 · 2 晚总价' : '经济舱',
            availability: '', booking_url: '', notes: ['报价需核实，非含税总价。'] }],
          source_title: '测试来源', source_url: 'https://www.12306.cn/', source_domain: '12306.cn',
          fetched_at: new Date().toISOString(), cached: false, query: request };
      }
      await route.fulfill({ json: body });
    });
    await page.goto(base);
    await page.evaluate(plan => {
      sessionStorage.setItem('tripPlan', JSON.stringify(plan));
      localStorage.setItem('tripstar-locale', 'zh-CN');
    }, plan);
    await page.goto(`${base}/result`);
    const panel = page.locator('.travel-search');
    await panel.waitFor();
    await panel.getByRole('button', { name: '查询火车高铁', exact: true }).click();
    await panel.locator('.travel-offer').waitFor();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].origin, '北京');
    await panel.getByRole('button', { name: '酒店住宿', exact: true }).click();
    await panel.getByLabel('入住晚数').fill('2');
    await panel.getByRole('button', { name: '查询酒店住宿', exact: true }).click();
    await panel.locator('.travel-offer').waitFor();
    assert.match(await panel.innerText(), /CNY 600/);
    assert.match(await panel.innerText(), /2 晚总价/);
    assert.equal(await panel.locator('.travel-offer strong').evaluate(element => getComputedStyle(element).color), 'rgb(255, 213, 161)', 'quote color must not inherit invisible parent styles');
    assert.equal(await panel.locator('.travel-offer').evaluate(element => getComputedStyle(element).backgroundColor), 'rgb(21, 35, 44)');
    assert.equal(calls[1].nights, 2);
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await panel.scrollIntoViewIfNeeded();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'page must not overflow');
      await panel.screenshot({ path: `artifacts/travel-${width}.png`, animations: 'disabled' });
    }
    await panel.getByRole('button', { name: '飞机航班', exact: true }).click();
    assert.equal(calls.length, 2, 'switching tabs must not query');
    const flightButton = panel.getByRole('button', { name: '查询飞机航班', exact: true });
    assert.ok(await flightButton.isDisabled(), 'paid consent required');
    assert.equal(await panel.getByLabel('出发城市三字码').inputValue(), 'BJS');
    await panel.getByLabel(/同意本次查询/).check();
    await flightButton.click();
    await panel.locator('.travel-offer').waitFor();
    assert.equal(calls.length, 3);
    assert.ok(calls[2].confirm_paid);
    assert.ok(await flightButton.isDisabled(), 'consent reset after query');
    assert.match(await panel.innerText(), /非含税总价/);
    await panel.getByLabel(/同意本次查询/).check();
    await panel.getByLabel('到达城市三字码').fill('CAN');
    assert.ok(await flightButton.isDisabled(), 'changed query invalidates consent');
    assert.equal(await panel.locator('.travel-offer').count(), 0, 'changed query must not retain old quote');
    responseStatus = 'empty';
    await panel.getByLabel(/同意本次查询/).check();
    await flightButton.click();
    await panel.getByText('没有符合条件的可用结果。').waitFor();
    enabled = false;
    await page.reload();
    await panel.getByText('此服务尚未启用，请先由管理员配置。原行程仍可正常使用。').waitFor();
    assert.ok(await panel.getByRole('button', { name: '查询火车高铁', exact: true }).isDisabled());
    assert.deepEqual(errors, []);
    console.log('PASS: train/hotel/flight forms, consent reset, no automatic calls, empty/disabled states, 390/1280 layout. All supplier responses mocked.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
