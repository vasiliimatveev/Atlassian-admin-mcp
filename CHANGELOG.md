# Changelog

## 0.1.0

First standalone release.

- 118 read-only tools in 14 toolsets plus `jira_analyst_status` self-check.
- Async HTTP client with connection pooling, a TTL cache, de-duplication of
  identical in-flight requests, a concurrency cap and retries.
- Structured errors for agents: `kind`, `status`, `hint`, `retryable`.
- Path-segment encoding for all arguments; attachment downloads are pinned to
  `JIRA_URL` and size-capped while streaming.
- Groovy endpoint 2.0.0: configurable `ALLOWED_GROUPS`, a `ping` action,
  HTTP 400 for unknown actions, and a system-log tail that reads from the end
  of the file and searches up to 50 MB.
- Dev-status tools accept issue keys as well as ids.
