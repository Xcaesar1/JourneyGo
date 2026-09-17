const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: process.env.HOME_UI_SYSTEM_PROXY ? [] : ['--no-proxy-server'] });
  try {
    const access = process.env.HOME_UI_AUTH_FILE ? JSON.parse(fs.readFileSync(process.env.HOME_UI_AUTH_FILE, 'utf8')) : null;
    const page = await browser.newPage(access ? { httpCredentials: { username: access.username, password: access.password } } : {});
    const errors = [];
    const writes = [];
    const externalFonts = [];
    const eagerResult = [];
    page.on('request', request => {
      if (/fonts\.(googleapis|gstatic)\.com/.test(request.url())) externalFonts.push(request.url());
      if (/\/Result[-.]/.test(request.url())) eagerResult.push(request.url());
    });
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', entry => {
      if (entry.text().includes('Failed to resolve component')) errors.push(entry.text());
    });
    await page.route('**/api/**', route => {
      if (route.request().method() === 'POST') writes.push(route.request().url());
      return route.fulfill({ json: { success: true, data: [], items: [] } });
    });
    const base = process.env.HOME_UI_URL || 'http://127.0.0.1:5174';
    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 60000 });
    const icon = page.locator('link[rel="icon"]');
    assert.equal(await icon.getAttribute('type'), 'image/png');
    const iconResponse = await page.request.get(new URL(await icon.getAttribute('href'), base).href);
    assert.equal(iconResponse.status(), 200);
    const digest = data => crypto.createHash('sha256').update(data).digest('hex');
    assert.equal(digest(await iconResponse.body()), digest(fs.readFileSync('frontend/favicon.png')));
    for (const [code, locale] of [['zh', 'zh-CN'], ['en', 'en-US']]) {
      const pack = JSON.parse(fs.readFileSync(`frontend/src/i18n/locales/${code}.json`, 'utf8'));
      await page.evaluate(locale => localStorage.setItem('tripstar-locale', locale), locale);
      for (const width of [390, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
        await page.locator('#hero-title').waitFor();
        assert.equal(await page.locator('#hero-title').textContent(), pack.home.hero.title);
        assert.equal(await page.locator('.settings-btn, .landing-cta, .presentation-title, .moving-clouds').count(), 0);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        const background = await page.locator('.journey-landscape').evaluate(el => getComputedStyle(el).backgroundImage);
        const url = background.match(/url\("?(.*?)"?\)/)[1];
        assert.equal((await page.request.get(url)).status(), 200);
        if (code === 'zh') await page.screenshot({ path: `artifacts/home-hero-${width}.png` });
      }
    }
    for (const previous of ['ja-JP', 'ko-KR']) {
      await page.evaluate(value => localStorage.setItem('tripstar-locale', value), previous);
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('#hero-title').waitFor();
      assert.equal(await page.evaluate(() => localStorage.getItem('tripstar-locale')), 'zh-CN');
      assert.equal(await page.locator('html').getAttribute('lang'), 'zh-CN');
    }
    await page.locator('.lang-select-nav').click();
    await page.locator('.ant-select-dropdown:visible').waitFor();
    assert.equal(await page.locator('.ant-select-dropdown:visible .ant-select-item-option').count(), 2);
    await page.keyboard.press('Escape');
    await page.setViewportSize({ width: 1440, height: 900 });
    const landscape = page.locator('.journey-landscape');
    assert.match(await landscape.evaluate(el => getComputedStyle(el).animationName), /^landscape-drift/);
    const initialTransform = await landscape.evaluate(el => getComputedStyle(el).transform);
    await page.waitForTimeout(500);
    assert.notEqual(await landscape.evaluate(el => getComputedStyle(el).transform), initialTransform);
    const scaleChange = await landscape.evaluate(el => {
      const animation = el.getAnimations()[0];
      const time = animation.currentTime;
      animation.pause();
      animation.currentTime = 0;
      const before = new DOMMatrixReadOnly(getComputedStyle(el).transform).a;
      animation.currentTime = 5000;
      const after = new DOMMatrixReadOnly(getComputedStyle(el).transform).a;
      animation.currentTime = time;
      animation.play();
      return after - before;
    });
    assert.ok(scaleChange > .02, 'camera movement should be noticeable within five seconds');
    assert.equal(await page.locator('.journey-motion-toggle').count(), 0);
    assert.equal(await landscape.evaluate(el => getComputedStyle(el).animationPlayState), 'running');
    await page.setViewportSize({ width: 390, height: 900 });
    assert.equal(await landscape.evaluate(el => getComputedStyle(el).animationName), 'none');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const selector of ['.journey-landscape', '.journey-mist', '.journey-sunlight']) {
      assert.equal(await page.locator(selector).evaluate(el => getComputedStyle(el).animationName), 'none');
    }
    assert.equal(await page.locator('.journey-motion-toggle').isVisible(), false);
    assert.equal(await page.locator('.journey-hero input, .journey-search').count(), 0);
    await page.locator('.ant-picker input').first().click();
    await page.locator('.ant-picker-dropdown:visible').waitFor();
    await page.keyboard.press('Escape');
    await page.locator('.special-textarea').fill('保留已有行程需求');
    await page.locator('.journey-explore').click();
    await page.waitForTimeout(800);
    assert.equal(await page.locator('.special-textarea').inputValue(), '保留已有行程需求');
    assert.ok(await page.evaluate(() => scrollY > 300));
    await page.locator('.journey-explore').click();
    assert.equal(await page.locator('.special-textarea').inputValue(), '保留已有行程需求');
    assert.deepEqual(writes, [], 'explore must not generate or make paid calls');
    assert.deepEqual(externalFonts, [], 'fonts must be served by this site');
    assert.deepEqual(eagerResult, [], 'result bundle must not be downloaded on the homepage');
    assert.deepEqual(errors, []);
    console.log('PASS: two homepage languages, saved locale fallback, phone/desktop, motion, explore preserves data');
  } finally { await browser.close(); }
})().catch(error => {
  // Playwright request errors can include authentication headers in call logs.
  console.error(`${error.name}: ${String(error.message).split('\n')[0]}`);
  process.exitCode = 1;
});
