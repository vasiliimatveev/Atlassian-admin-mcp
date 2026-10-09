# jira-dc-analyst-mcp

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
  with an explicit `truncated` marker. `jira_analyst_status` diagnoses setup
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
uvx jira-dc-analyst-mcp --list-toolsets
```

Claude Desktop / Claude Code / Cursor:

```json
{
  "mcpServers": {
    "jira-dc-analyst": {
      "command": "uvx",
      "args": ["jira-dc-analyst-mcp"],
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
jira-dc-analyst-mcp --transport http --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker build -t jira-dc-analyst-mcp .
docker run --rm -i --env-file .env jira-dc-analyst-mcp
```

Then ask your agent: *"Run jira_analyst_status"*, *"Which workflows use a
ScriptRunner post-function that touches the Assignee field?"*, *"Who can
administer project HR and through which scheme grant?"*

## Installing the Groovy endpoint

Most `admin`, `scriptrunner`, `jmwe`, `structure` and `assets` tools need it.
The other toolsets use plain REST APIs.

1. In Jira, open **ScriptRunner → REST Endpoints → Create → Custom endpoint**.
2. Paste [`groovy/admin_analyst.groovy`](groovy/admin_analyst.groovy) and save.
3. If your admin group is not `jira-administrators`, edit `ALLOWED_GROUPS` at
   the top of the script.
4. Call `jira_analyst_status`. Its `groovyEndpoint.endpointVersion` should read `2.0.0`.

The endpoint is served at `/rest/scriptrunner/latest/custom/adminAnalyst`.
Set `JIRA_ANALYST_SR_PATH` if yours lives elsewhere.

## Configuration

All settings are environment variables. [`.env.example`](.env.example) documents each one.

| Variable | Default | |
|---|---|---|
| `JIRA_URL` | — | Base URL, including the context path if Jira has one |
| `JIRA_PERSONAL_TOKEN` | — | Or `JIRA_USERNAME` + `JIRA_API_TOKEN`/`JIRA_PASSWORD` |
| `TOOLSETS` | `default` | `default` = admin, logs, integrations, issue_inspect, properties; `all` = everything |
| `JIRA_SSL_VERIFY` | `true` | `false`, or a path to a CA bundle |
| `JIRA_ANALYST_CACHE_TTL` | `120` | Seconds; `0` turns the cache off |
| `JIRA_ANALYST_MAX_CONCURRENCY` | `8` | Parallel requests to Jira |
| `JIRA_ANALYST_MAX_RESPONSE_CHARS` | `100000` | Longer results are truncated with a marker |

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

To add a tool, put a decorated function in the matching `src/jira_dc_analyst/tools/<toolset>.py`.
The tests check that it has a description, documented parameters and
read-only annotations, call it against a fake Jira, and fail if
`TOOLS.md` is stale.

## License

MIT. Not an official Atlassian product; Jira and Atlassian are trademarks of Atlassian.
