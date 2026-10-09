# Changelog

## 0.1.0

First standalone release.

- Issue guard (`JIRA_GUARD_JQL`, `JIRA_GUARD_HEADER`). It confines every call
  to the issues matched by a JQL, with the allow-list, case-insensitive keys,
  path-trick, attachment, header and redirect protections described in the
  README.

- 118 read-only tools in 14 toolsets plus `jira_admin_status` self-check.
- Async HTTP client with connection pooling, a TTL cache, de-duplication of
  identical in-flight requests, a concurrency cap and retries.
- Structured errors for agents: `kind`, `status`, `hint`, `retryable`.
- Path-segment encoding for all arguments; attachment downloads are pinned to
  `JIRA_URL` and size-capped while streaming.
- Groovy endpoint 2.0.0: configurable `ALLOWED_GROUPS`, a `ping` action,
  HTTP 400 for unknown actions, and a system-log tail that reads from the end
  of the file and searches up to 50 MB.
- Dev-status tools accept issue keys as well as ids.
