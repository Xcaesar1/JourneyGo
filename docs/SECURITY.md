# Security Boundaries

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
- PostgreSQL is canonical. Redis data may be discarded and recovered from durable task state.
- Container logs rotate at 10 MiB with three files; services have CPU and memory limits and long-running application
  processes run as UID `10001`. A one-shot root `data-init` only fixes named-volume ownership and then exits.

## Reporting

Do not open a public issue containing a credential, Cookie, raw production payload or unredacted log. Revoke the
affected credential first, then provide a minimal redacted reproduction and diagnostic `trace_id`.
