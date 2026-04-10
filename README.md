# lawyer-mcp

MCP (Model Context Protocol) server for Legalize.dev: AI tools to query and understand legal frameworks across countries.

Goal: help an AI quickly answer questions about a country’s legal framework by querying Legalize.dev’s structured legislation API.

## Status
Work in progress.

## Data source
- API docs (Swagger): https://legalize.dev/api/docs
- OpenAPI spec: https://legalize.dev/openapi.json

## Auth
Legalize.dev uses a bearer token in the `Authorization` header (see `components.securitySchemes.ApiKeyAuth` in the OpenAPI spec).

This server expects:

- `LEGALIZE_API_KEY` env var (either the raw `leg_...` token or the full `Bearer leg_...` value)

### TLS / certificates (Codex on Windows)

If you hit errors like `certificate verify failed: certificate signature failure`, your Python/Codex environment may be missing the right CA bundle.

Options:
- Prefer installing/updating CA certificates in your environment (recommended).
- Set `LEGALIZE_SSL_CERT_FILE=/path/to/ca-bundle.pem` to point to a CA bundle.
- If `certifi` is installed, lawyer-mcp will automatically use it.
- As a last resort (NOT recommended): `LEGALIZE_SSL_INSECURE=1` disables certificate verification.

## Tools (MCP)

Tools are derived from `https://legalize.dev/openapi.json`.

### Toolset selection

By default we expose a **full** read-only toolset. If you want the smallest useful surface area (to reduce model confusion), set:

- `LEGALIZE_TOOLSET=minimal`

**Minimal toolset includes:**

- `legalize_openapi_summary` — public summary of the OpenAPI spec (no API key)
- `legalize_countries` — list supported countries
- `legalize_jurisdictions` — list jurisdictions within a country
- `legalize_laws` — search/list laws within a country (single page)
- `legalize_laws_all` — same, but auto-paginates (best-effort flattening)
- `legalize_law_meta` — lightweight law metadata
- `legalize_law_get` — full law payload
- `legalize_reforms` — list reforms/diffs for a law

**Full toolset additionally includes:**

- `legalize_commits` — list git commits for a law
- `legalize_law_at_commit` — fetch law content at a commit SHA
- `legalize_rangos` — list legal hierarchy/ranks (rangos)
- `legalize_stats` — summary statistics per country (optional jurisdiction)
- `legalize_account` — current API key account/usage/limits (does not count against quota)

### Dangerous tool (opt-in)

- `legalize_rotate_key` — rotate API key (invalidates current key). Disabled by default; enable with `LEGALIZE_ENABLE_DANGEROUS_TOOLS=1`.

## Install

For now this is a single-file Python module (no external dependencies).

### Option A: run from source (recommended)

```bash
git clone https://github.com/pugafran/lawyer-mcp.git
cd lawyer-mcp

# required
export LEGALIZE_API_KEY="leg_..."   # or "Bearer leg_..."

python3 -m lawyer_mcp
```

### Option B: pipx / pip (if you have pip available)

```bash
pipx install git+https://github.com/pugafran/lawyer-mcp.git
# or: python -m pip install git+https://github.com/pugafran/lawyer-mcp.git

export LEGALIZE_API_KEY="leg_..."
lawyer-mcp
```

## Configure in Claude Desktop (MCP)

1) Install the server (see Install above).
2) Open Claude Desktop → **Settings** → **Developer** → **Edit MCP config**.
3) Add a server entry like this:

```json
{
  "mcpServers": {
    "lawyer": {
      "command": "python3",
      "args": ["-m", "lawyer_mcp"],
      "env": {
        "LEGALIZE_API_KEY": "leg_...",
        "LEGALIZE_TOOLSET": "minimal"
      }
    }
  }
}
```

Restart Claude Desktop. You should then see the `legalize_*` tools available.

## Configure in OpenAI Codex / IDEs

Codex support depends on the client you are using (Codex CLI vs an IDE with MCP support).

If your Codex/IDE supports MCP servers via a JSON config, use the same command/env as above:

- command: `python3`
- args: `-m lawyer_mcp`
- env: `LEGALIZE_API_KEY=...`

If you tell me which “Codex” you mean (Codex CLI, VS Code extension, Cursor, etc.), I’ll add an exact, copy/paste config snippet for that client.

## Run

```bash
# required
export LEGALIZE_API_KEY="leg_..."   # or "Bearer leg_..."

# optional (useful for tests/self-hosted mirrors)
# export LEGALIZE_BASE_URL="https://legalize.dev"
# export LEGALIZE_HTTP_RETRIES=2
# export LEGALIZE_HTTP_TIMEOUT=30

# optional (DANGEROUS): exposes `legalize_rotate_key`
# export LEGALIZE_ENABLE_DANGEROUS_TOOLS=1

python3 -m lawyer_mcp
```
