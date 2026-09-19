# Security Guide

## Public Deployment Defaults

- Set `DEMO_MODE=false` for real planning and `API_ACCESS_CODE_REQUIRED=true` before public exposure.
- Keep `RUNTIME_SECRET_UPDATES_ENABLED=false`; provision Secret values only through an untracked environment file
  or a deployment Secret manager.
- Keep `API_DOCS_ENABLED=false` unless interactive API documentation is intentionally public.
- Bind Compose to loopback and expose only Caddy or Nginx over HTTPS.
- Restrict the AMap Web JS Key and security code to approved HTTPS domains in the AMap console.
- Rotate model, map and community credentials if they have ever appeared in a browser response, console, chat,
  repository, CI log or terminal transcript.

## Secret Classification

| Value | Browser | Repository | Application log | Provisioning boundary |
| --- | --- | --- | --- | --- |
| LLM API key | Never | Never | Never | Server environment only |
| AMap Web Service key | Never | Never | Never | Server environment only |
| Xiaohongshu Cookie | Never | Never | Never | Server environment only |
| API access code | Never | Never | Never | Reverse proxy/client header and server environment |
| AMap Web JS Key/security code | Required by map JS | Never populated | Never | Server environment to browser; domain restricted |

`GET /api/settings` may expose the browser AMap JS Key and security code because they are required by map JavaScript,
but it only returns booleans for server-side Provider configuration. `PUT /api/settings` returns `403` unless
runtime updates are explicitly enabled and a valid `X-Access-Code` is supplied.

## Operational Controls

- API request size, rate, active task count, model token and model cost limits are enforced before or during work.
- Trace records exclude request payloads, prompts, model output, authorization headers, keys and Cookies.
- Upstream failures are mapped to fixed error codes; raw credential-bearing URLs and exception bodies are not
  returned to clients.
- PostgreSQL is canonical for tasks. Redis also holds non-expiring paid flight counters: never discard or
  reset those counters during cleanup, recovery or namespace migration.
- Container logs rotate at 10 MiB with three files; services have CPU and memory limits and long-running application
  processes run as UID `10001`. A one-shot root `data-init` only fixes named-volume ownership and then exits.

## Credential Audit - 2026-09-19

- Fetched `origin` before checking. Scanned 94 reachable commits with Gitleaks 8.30.1 and fully redacted reports.
- Compared nine current staging/access credentials privately against reachable Git patch history, including
  `origin/main`; no exact matches. Runtime settings were also checked without printing secret values.
- One history finding points to an `xsec_token` in the bundled signature script's test function, introduced
  in commit `c9c9b26`. It does not match the current credentials checked above; validity was not tested.
  Current example token/Cookie literals have been replaced with placeholders. Existing history was not rewritten.
- A fresh snapshot of repository files, including pending edits, passed Gitleaks with no findings.
  This result does not mean the historical finding was erased or prove that unknown/revoked credentials never existed.
- Environment examples, Git ignore rules and Docker build-context exclusions now have regression checks.
  See `API_KEYS.md` for feature-specific requirements and placeholders. No running credentials or quotas were changed.

## Reporting A Leak

Do not open a public issue containing a credential, Cookie, raw production payload or unredacted log. Revoke the
affected credential first, then provide a minimal redacted reproduction and diagnostic `trace_id`.
