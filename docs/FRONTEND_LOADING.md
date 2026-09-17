# Frontend Loading Verification

## Scope

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
- Current Caddy staging configuration adds `Cache-Control: no-store` globally. Changing ingress requires approval. At publication, retain no-store for HTML, API and authentication/error responses; allow successful `/assets` responses to retain the application's private cache policy. Preserve Basic Auth and other security headers.
- Validate public JS/CSS Content-Encoding and Vary headers, private immutable cache headers for hashed assets, revalidation of HTML, and unauthenticated rejection. Do not claim browser-cache improvements until these checks pass through ingress.
- Recheck root and direct `/result` navigation, local fonts, mobile layout and normal/reduced motion. Use explicit waits for mounted controls rather than treating document load as Vue readiness.
- Existing large background PNG and favicon are unchanged. The initial JS reduction does not eliminate those downloads or guarantee a specific cellular-network load time.

## Rollback

- Restore the prior application image and any separately approved ingress change. No database rollback or migration is required.
