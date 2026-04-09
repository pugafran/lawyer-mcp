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

## Run

```bash
# required
export LEGALIZE_API_KEY="leg_..."   # or "Bearer leg_..."

# optional (useful for tests/self-hosted mirrors)
# export LEGALIZE_BASE_URL="https://legalize.dev"
# export LEGALIZE_HTTP_RETRIES=2
# export LEGALIZE_HTTP_TIMEOUT=30

python3 -m lawyer_mcp
```
