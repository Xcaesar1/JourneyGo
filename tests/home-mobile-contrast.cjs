const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  fs.mkdirSync('artifacts/mobile-adb', { recursive: true });
  const remote = process.env.MOBILE_CDP_URL;
  const browser = remote
    ? await chromium.connectOverCDP(remote)
    : await chromium.launch({ channel: 'chrome', headless: true });
  const context = remote ? browser.contexts()[0] : await browser.newContext({ viewport: { width: 363, height: 705 }, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const base = process.env.HOME_UI_URL || 'http://127.0.0.1:5174';
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', route => route.fulfill({ json: route.request().url().includes('/travel/capabilities')
    ? { one_click: { enabled: true }, train: { enabled: true }, hotel: { enabled: true }, flight: { enabled: false } }
    : { success: true, data: [], items: [] } }));
  try {
    for (const locale of ['zh-CN', 'en-US']) {
      await page.goto(base, { waitUntil: 'networkidle' });
      await page.evaluate(value => localStorage.setItem('tripstar-locale', value), locale);
      await page.reload({ waitUntil: 'networkidle' });
      await page.locator('.planning-hint').first().waitFor();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const landscape = await page.locator('.journey-landscape').evaluate(el => {
        const rect = el.getBoundingClientRect();
        return { width: rect.width, height: rect.height, size: getComputedStyle(el).backgroundSize, position: getComputedStyle(el).backgroundPosition, repeat: getComputedStyle(el).backgroundRepeat, viewport: innerWidth, heroHeight: document.querySelector('.journey-hero').getBoundingClientRect().height };
      });
      assert.equal(landscape.size, 'cover');
      assert.equal(landscape.position, '80% 50%');
      assert.equal(landscape.repeat, 'no-repeat');
      assert.ok(Math.abs(landscape.width - landscape.viewport) < 1);
      assert.ok(Math.abs(landscape.height - landscape.heroHeight) < 1, 'background fills hero behind the text');
      const memories = await page.locator('.memories-entry').boundingBox();
      assert.ok(memories.height <= 32, 'memories button should be compact');
      const explore = await page.locator('.journey-explore').evaluate(el => ({ width: el.getBoundingClientRect().width, padding: parseFloat(getComputedStyle(el).paddingLeft), gap: parseFloat(getComputedStyle(el).gap) }));
      assert.ok(explore.padding <= 14 && explore.gap <= 10);
      if (locale === 'zh-CN') assert.ok(explore.width <= 125);
      assert.equal(await page.locator('.lang-select-nav .ant-select-selection-item').evaluate(el => getComputedStyle(el).textAlign), 'center');
      await page.screenshot({ path: `artifacts/mobile-adb/updated-hero-${locale}.png` });
      await page.locator('.planning-preferences summary').click();
      for (const selector of ['.planning-hint', '.planning-preferences summary', '.field-label', '.step-head h3', '.step-head span', '.interest-pill', '.discovery-heading p', '.discovery-load-btn', '.submit-btn']) {
        const colors = await page.locator(selector).evaluateAll(nodes => nodes.map(el => getComputedStyle(el).color));
        assert.ok(colors.length > 0, selector);
        assert.ok(colors.every(color => color === 'rgb(255, 255, 255)'), `${selector}: ${colors.join(', ')}`);
      }
      await page.locator('.planning-hint').first().scrollIntoViewIfNeeded();
      await page.screenshot({ path: `artifacts/mobile-adb/updated-preferences-${locale}.png` });
      await page.locator('.submit-btn').scrollIntoViewIfNeeded();
      await page.screenshot({ path: `artifacts/mobile-adb/updated-submit-${locale}.png` });
    }
    assert.deepEqual(errors, []);
    console.log(`PASS: ${remote ? 'real Android Chrome' : 'mobile viewport'}, Chinese/English, right-focused full hero background, compact buttons, centered language, white form text, no overflow; APIs mocked.`);
  } finally {
    await page.close();
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
