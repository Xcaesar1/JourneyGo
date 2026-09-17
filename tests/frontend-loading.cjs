// Run against a production build served with backend/app/api/static_assets.py.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', route => route.fulfill({ json: { success: true, data: [], items: [] } }));
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 200000, uploadThroughput: 100000 });
    const mainResponse = page.waitForResponse(response => /\/assets\/index-[^/]+\.js$/.test(response.url()));
    const start = Date.now();
    await page.goto(process.env.FRONTEND_LOADING_URL || 'http://127.0.0.1:5174', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.locator('.journey-explore').waitFor();
    const interactiveMs = Date.now() - start;
    const response = await mainResponse;
    assert.equal(response.headers()['content-encoding'], 'gzip');
    assert.match(response.headers()['cache-control'], /private.*immutable/);
    const resources = await page.evaluate(() => performance.getEntriesByType('resource').map(r => ({ name: r.name, encoded: r.encodedBodySize, decoded: r.decodedBodySize })));
    const main = resources.find(r => /\/assets\/index-[^/]+\.js$/.test(r.name));
    assert.ok(main.encoded < 350000 && main.decoded < 1100000);
    assert.equal(resources.some(r => /\/(Result|Memories)-|\/api\/trip\/history|fonts\.googleapis|fonts\.gstatic/.test(r.name)), false);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ simulatedMbps: 1.6, latencyMs: 150, interactiveMs, scriptEncodedBytes: main.encoded, scriptDecodedBytes: main.decoded }));
  } finally { await browser.close(); }
})().catch(error => { console.error(String(error.message).split('\n')[0]); process.exitCode = 1; });
