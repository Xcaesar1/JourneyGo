// Run against staging with the output of backend.scripts.weather_smoke.
const { chromium } = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
  const auth = JSON.parse(fs.readFileSync(process.env.WEATHER_AUTH_FILE, 'utf8'));
  const sample = JSON.parse(fs.readFileSync(process.env.WEATHER_SMOKE_FILE, 'utf8'));
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-proxy-server'] });
  try {
    const context = await browser.newContext({
      httpCredentials: { username: auth.username, password: auth.password },
      viewport: { width: 390, height: 844 },
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(auth.url);
    await page.evaluate(plan => {
      sessionStorage.setItem('tripPlan', JSON.stringify(plan));
      localStorage.setItem('journeygo-locale', 'zh-CN');
    }, sample.data);
    await page.goto(new URL('/result', auth.url).href);
    const nav = page.locator('.mobile-section-nav');
    await nav.getByRole('button', { name: '天气信息', exact: true }).click();
    const panel = page.locator('#weather');
    await panel.waitFor({ state: 'visible' });
    assert.match(await panel.innerText(), /Open-Meteo/);
    assert.match(await panel.innerText(), /CC BY 4.0/);
    const items = panel.locator('.today-info-item');
    assert.match(await items.nth(2).innerText(), new RegExp(`${sample.data.weather_info[0].precipitation_probability}%`));
    assert.match(await items.nth(3).innerText(), /--/);
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await panel.isVisible());
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const dashboard = await panel.locator('.weather-dashboard').boundingBox();
      const attribution = await panel.getByRole('link', { name: /Weather data by/ }).boundingBox();
      assert.ok(attribution.y + attribution.height <= dashboard.y + dashboard.height + 1, 'attribution must not be clipped');
      await page.screenshot({ path: `artifacts/weather-${width}.png`, fullPage: true, animations: 'disabled' });
    }
    await page.evaluate(() => {
      const plan = JSON.parse(sessionStorage.getItem('tripPlan'));
      plan.weather_info = [];
      sessionStorage.setItem('tripPlan', JSON.stringify(plan));
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await nav.getByRole('button', { name: '天气信息', exact: true }).click();
    assert.match(await panel.innerText(), /16/);
    assert.equal(await panel.locator('.weather-dashboard').count(), 0);
    assert.deepEqual(errors, []);
    console.log('PASS: live weather payload, mobile/desktop display, attribution, numeric values, empty state; no page errors.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
