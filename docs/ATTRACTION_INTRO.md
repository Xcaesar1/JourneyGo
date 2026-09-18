# Attraction Introductions

- GET `/api/poi/intro?name=...&city=...` reads the public Chinese Wikipedia
  Action API. No API key, model generation or paid provider is used.
- Exact-title queries follow redirects and include explicit parenthesized aliases
  in the same request (for example, a POI ending in `(博文女校)`). Require the destination
  city in the lead text and reject disambiguation/missing pages. Unmatched overview
  cards state that no verified background is available; no fuzzy substitution is used.
- Excerpts are at most 30 characters, usually 20-30. Remove parenthetical text
  and citations, prefer a nearby punctuation boundary, otherwise show ellipsis.
- Overview and daily attraction cards share request deduplication and a
  three-request concurrency limit. Fetch independently from trip generation;
  do not modify saved plans. Keep reservation/opening/ticket uncertainty notices.
- Include article attribution, an excerpt label and CC BY-SA 4.0 license link.
  Source: https://www.mediawiki.org/wiki/Wikimedia_APIs/Content_reuse
- Backend cache: maximum 512 entries per process, 24-hour positive / 5-minute
  negative TTL. Provider failure returns empty data. HTTP timeout: 8 seconds.
- Tests: `backend/tests/test_attraction_intro.py`, frontend
  `src/views/Result.images.test.mjs`, production build and mocked mobile/desktop
  browser checks. Public API connectivity was checked separately from staging
  against three sample landmarks; no application deployment was performed.
