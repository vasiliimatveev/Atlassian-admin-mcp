# Atlassian Admin MCP

A read-only [MCP](https://modelcontextprotocol.io) server that lets AI agents
**audit a Jira Data Center instance the way an administrator would**:
workflows down to individual validators and post-functions, every scheme,
screens, custom-field contexts, licensing, ScriptRunner / JMWE Groovy source,
Structure, Assets (Insight), Automation for Jira, Git integration, SLA and
time-in-status plugins, audit and system logs.

The stock Jira REST API cannot see most of this. A small Groovy endpoint that
you install through ScriptRunner closes the gap. The endpoint is read-only and
limited to admin groups.

**118 read-only tools in 14 toolsets.** See the full list in [TOOLS.md](TOOLS.md).

- **Read-only by design.** Every tool carries `readOnlyHint`, the Groovy endpoint
  answers GET only, and no code path writes to Jira.
- **Built for agents.** Results are compact JSON. Errors come back as `isError`
  results with a stable `kind` (`not_found`, `groovy_endpoint_missing`,
  `auth_failed`, …), a `hint` and a `retryable` flag. Oversized results are cut
  with an explicit `truncated` marker. `jira_admin_status` diagnoses setup
  problems in one call.
- **Fast.** The server keeps one pooled async HTTP client, caches configuration
  reads for a short TTL, merges identical requests that are in flight at the
  same time, retries on 429/5xx with backoff, and caps concurrency so Jira is
  not overloaded.
- **Safe with untrusted input.** Arguments are encoded per path segment, so a
  value cannot jump to another REST endpoint. Attachment downloads never send
  credentials to a host other than `JIRA_URL` and are size-capped while
  streaming.

## Quick start

```bash
uvx atlassian-admin-mcp --list-toolsets
```

Claude Desktop / Claude Code / Cursor:

```json
{
  "mcpServers": {
    "atlassian-admin": {
      "command": "uvx",
      "args": ["atlassian-admin-mcp"],
      "env": {
        "JIRA_URL": "https://jira.example.com",
        "JIRA_PERSONAL_TOKEN": "<personal access token>",
        "TOOLSETS": "default,scriptrunner"
      }
    }
  }
}
```

HTTP transport (for gateways such as LiteLLM, or for shared deployments):

```bash
atlassian-admin-mcp --transport http --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker build -t atlassian-admin-mcp .
docker run --rm -i --env-file .env atlassian-admin-mcp
```

Then ask your agent: *"Run jira_admin_status"*, *"Which workflows use a
ScriptRunner post-function that touches the Assignee field?"*, *"Who can
administer project HR and through which scheme grant?"*

## Installing the Groovy endpoint

Most `admin`, `scriptrunner`, `jmwe`, `structure` and `assets` tools need it.
The other toolsets use plain REST APIs.

1. In Jira, open **ScriptRunner → REST Endpoints → Create → Custom endpoint**.
2. Paste [`groovy/atlassian_admin.groovy`](groovy/atlassian_admin.groovy) and save.
3. If your admin group is not `jira-administrators`, edit `ALLOWED_GROUPS` at
   the top of the script.
4. Call `jira_admin_status`. Its `groovyEndpoint.endpointVersion` should read `2.0.0`.

The endpoint is served at `/rest/scriptrunner/latest/custom/atlassianAdmin`.
Set `JIRA_ADMIN_SR_PATH` if yours lives elsewhere.

## Issue guard (multi-user / restricted access)

When an agent serves several users, or should only ever see some projects,
turn on the guard. It confines every call to the issues matched by a JQL:

```bash
JIRA_GUARD_JQL='project in (SOS, HR)'          # static, works over stdio
JIRA_GUARD_HEADER=x-jira-guard-jql             # per request, e.g. LiteLLM static headers
```

When both variables are set, the two conditions are combined with AND. The
server enforces the guard at its single HTTP choke point, so no tool can get
around it:

- **JQL parameters.** They are rewritten to `(<guard>) AND (<jql>) [ORDER BY …]`.
  The server rejects unbalanced parentheses or quotes, and anything after
  `ORDER BY` other than a plain sort list.
- **Issue references.** A key or numeric id in the path or query is first
  checked with `(<guard>) AND issuekey in (…)`. Keys are matched without regard
  to case, just as Jira DC matches them. Anything that is not exactly a key or
  id is refused: `;`, `\`, encoded `/`, double encoding, JQL fragments.
- **Attachments.** Their metadata and files are served only after their issue
  passed the check in the same call, so pass `issue_key`. Download links that
  point at another host or at another file are refused.
- **Allow-list.** Only endpoints and query parameters on an explicit
  allow-list are accepted. Admin and configuration tools, including the Groovy
  endpoint, cannot be confined by JQL, so they are hidden and blocked.
- **Header mode.** The header must be present exactly once on every call.
  Any `X-Atlassian-*` header causes a refusal.
- **Fail closed.** Redirects are never followed, and any error during a check
  denies the call. A refusal returns `kind: "guard_denied"`.

## Configuration

All settings are environment variables. [`.env.example`](.env.example) documents each one.

| Variable | Default | |
|---|---|---|
| `JIRA_URL` | — | Base URL, including the context path if Jira has one |
| `JIRA_PERSONAL_TOKEN` | — | Or `JIRA_USERNAME` + `JIRA_API_TOKEN`/`JIRA_PASSWORD` |
| `TOOLSETS` | `default` | `default` = admin, logs, integrations, issue_inspect, properties; `all` = everything |
| `JIRA_SSL_VERIFY` | `true` | `false`, or a path to a CA bundle |
| `JIRA_ADMIN_CACHE_TTL` | `120` | Seconds; `0` turns the cache off |
| `JIRA_ADMIN_MAX_CONCURRENCY` | `8` | Parallel requests to Jira |
| `JIRA_ADMIN_MAX_RESPONSE_CHARS` | `100000` | Longer results are truncated with a marker |
| `JIRA_GUARD_JQL` / `JIRA_GUARD_HEADER` | — | Issue guard, see above |

Each enabled tool adds its schema to the model's context. The `default` set
costs about 10k tokens and `all` about 19k. Enable only the plugin toolsets you
actually have installed.

## Development

```bash
uv sync
uv run pytest            # unit + end-to-end tests, no Jira needed
uv run ruff check . && uv run ruff format --check .
uv run python scripts/gen_tools_md.py   # after adding or renaming tools
```

To add a tool, put a decorated function in the matching `src/atlassian_admin_mcp/tools/<toolset>.py`.
The tests check that it has a description, documented parameters and
read-only annotations, call it against a fake Jira, and fail if
`TOOLS.md` is stale.

## License

MIT. Not an official Atlassian product; Jira and Atlassian are trademarks of Atlassian.
