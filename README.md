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

## Run (planned)

```bash
python -m lawyer_mcp
```
