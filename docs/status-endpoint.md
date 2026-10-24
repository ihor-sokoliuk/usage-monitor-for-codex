# Local usage endpoint

Enable `"status_server_enabled": true` in `usage-monitor-for-codex-settings.json` to let local programs read cached Codex usage. The endpoint is disabled by default. It binds only to `127.0.0.1`; the default port is `45457`. Set `status_server_port` to an integer from 1024 to 65535 to change it. Use a different port for each simultaneously running monitor. A port conflict leaves the monitor running without the endpoint.

`GET /usage` and `GET /` return JSON containing `schema: 1`, a UTC `generated_at` response timestamp, and only `providers.codex`. That provider object contains `display_name`, `stale`, `error`, and a dynamic `windows` map of normalized `utilization` and `resets_at` values. Before any successful fetch, `stale` is null; after more than three poll intervals without a successful fetch it is true. Errors use a generic message. Profiles, account emails, credentials, raw provider payloads, and extra-usage billing details are excluded.

Requests read memory and never trigger a provider fetch or write a snapshot file. Unknown paths return 404; unsupported methods return 405 with `Allow: GET`. Responses use `Cache-Control: no-store`. No CORS headers are sent. The endpoint has no authentication: other local programs can read it when enabled. Loopback binding is not a browser authentication boundary. Quit and Restart release the listener.
