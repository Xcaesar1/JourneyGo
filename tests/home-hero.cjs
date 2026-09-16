const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-proxy-server'] });
  try {
    const page = await browser.newPage();
    const errors = [];
    const writes = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', route => {
      if (route.request().method() === 'POST') writes.push(route.request().url());
      return route.fulfill({ json: { success: true, data: [], items: [] } });
    });
    const base = process.env.HOME_UI_URL || 'http://127.0.0.1:5174';
    await page.goto(base);
    for (const [code, locale] of [['zh', 'zh-CN'], ['en', 'en-US'], ['ja', 'ja-JP'], ['ko', 'ko-KR']]) {
      const pack = JSON.parse(fs.readFileSync(`frontend/src/i18n/locales/${code}.json`, 'utf8'));
      await page.evaluate(locale => localStorage.setItem('tripstar-locale', locale), locale);
      for (const width of [390, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        await page.reload();
        await page.locator('#hero-title').waitFor();
        assert.equal(await page.locator('#hero-title').textContent(), pack.home.hero.title);
        assert.equal(await page.locator('.settings-btn, .landing-cta, .presentation-title, .moving-clouds').count(), 0);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        const background = await page.locator('.journey-hero').evaluate(el => getComputedStyle(el).backgroundImage);
        const url = background.match(/url\("?(.*?)"?\)/)[1];
        assert.equal((await page.request.get(url)).status(), 200);
        if (code === 'zh') await page.screenshot({ path: `artifacts/home-hero-${width}.png` });
      }
    }
    await page.locator('.journey-search input').fill('西安到成都，喜欢徒步');
    await page.locator('.journey-search input').press('Enter');
    await page.waitForTimeout(800);
    assert.equal(await page.locator('.special-textarea').inputValue(), '西安到成都，喜欢徒步');
    assert.ok(await page.evaluate(() => scrollY > 300));
    await page.locator('.journey-explore').click();
    assert.equal(await page.locator('.special-textarea').inputValue(), '西安到成都，喜欢徒步');
    assert.deepEqual(writes, [], 'explore must not generate or make paid calls');
    assert.deepEqual(errors, []);
    console.log('PASS: 4 languages, phone/desktop, image loads, no overflow/settings, search handoff and no generation');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
