# Frontend Loading Verification

## Scope

- Keep the homepage history-free. Its Memories entry sits between GitHub and the language selector; `/history` is lazy-loaded and requests at most 50 records only when opened.
- Preserve the planning draft and selected candidates only in memory while visiting Memories; browser reload clears that draft. Return from a result preserves the list and scroll position. Refresh failures keep existing records visible.
- Run `node tests/memories-ui.cjs` against the production build for navigation, four-language responsive layouts, empty/error/retry states and draft restoration. All APIs are mocked; no paid queries are required.
- Load Result.vue with a route import; keep homepage controls immediately available.
- Register only shared/homepage Ant Design components globally; import result-only components locally. Do not restore the full Antd plugin. Browser tests detect unresolved components and exercise date selection.
- Keep html2canvas behind dynamic imports in export actions. The result regression verifies no initial screenshot-library request and a successful PNG download after clicking export.
- Serve fonts from pinned `@fontsource` packages. Preserve their bundled OFL licenses; do not reintroduce external font stylesheets.
- Compress only the static asset mount, not API or SSE routes.
- Cache hashed assets privately with immutable URLs; revalidate HTML so it discovers new hashes. Never apply immutable caching to API responses or credentials.

## Verification

1. Run `npm --prefix frontend ci`, `npm --prefix frontend test`, and `npm --prefix frontend run build`.
2. Run `python -m pytest backend/tests` from the repository root.
3. Serve the production build using the API static asset implementation on port 5174. With Playwright available on NODE_PATH, run `node tests/home-hero.cjs`, `node tests/travel-ui.cjs` and `node tests/frontend-loading.cjs`.
4. The loading test uses a fresh browser and simulated 1.6 Mbps / 150 ms latency. It checks gzip, asset cache headers, no external font requests and no eager Result bundle. It measures button availability, not complete background image download. Supplier/API responses are mocked.

Measured on 2026-09-17 after selective component loading: initial JS 955448 decoded bytes / 309646 gzip bytes; button available in 2777 ms in one local emulated run. The preceding local run was 1754898 decoded bytes / 547969 gzip bytes and 4274 ms. These are diagnostic samples, not production latency guarantees. The loading test enforces a 1.1 MB decoded / 350 KB encoded initial-script budget.

## Staging Publication

- Rebuild the normal root Dockerfile; preserve the current release's private variables, provider flags, volumes and rollback image.
- On 2026-09-17, with explicit user approval, staging ingress was changed to retain no-store for HTML, API and authentication/error responses while caching successful hashed assets privately. Basic Auth and other security headers remain enabled. Caddy 2.6.2 requires explicit `defer` blocks, not the newer `>Header` or header response `match` syntax. Use reverse_proxy response matchers (200/304 plus upstream immutable cache policy) for the asset override and 4xx/5xx matchers for no-store; handle_errors also sets no-store.
- Validate public JS/CSS Content-Encoding and Vary headers, private immutable cache headers for hashed assets, revalidation of HTML, and unauthenticated rejection. Do not claim browser-cache improvements until these checks pass through ingress.
- Recheck root and direct `/result` navigation, local fonts, mobile layout and normal/reduced motion. Use explicit waits for mounted controls rather than treating document load as Vue readiness.
- Existing large background PNG and favicon are unchanged. The initial JS reduction does not eliminate those downloads or guarantee a specific cellular-network load time.

Deployment verification on 2026-09-17: public main JS gzip transfer 309939 bytes; HTML/API/401/404 no-store; assets private immutable without conflicting no-store; ETag 304; real Chrome return visit reused main JS cache. Home and travel/result browser regressions passed on staging with supplier APIs mocked, including PNG export. For cache verification, do not use Playwright routing or httpCredentials interception, which can disable cache; send the private Basic Auth header only to the trusted staging origin instead, without logging it.

## Rollback

- Restore the prior application image and any separately approved ingress change. No database rollback or migration is required.
- Current release: `/opt/tripstar/releases/loading-f46af59-20260917`; prior image: `journeyops-app:ambient-8499c3c`. The original ingress backup is `caddy-staging.before` in the release directory, mode 0600. Restore it with `sudo cp` (without `-p`) to `/etc/caddy/journeyops-staging.caddy`, validate `/etc/caddy/Caddyfile`, then gracefully reload Caddy. Never print the backup or expanded configuration because they contain credentials.
