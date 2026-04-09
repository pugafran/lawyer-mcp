#!/usr/bin/env python3

from __future__ import annotations

import io
import json
import os
import sys
import traceback
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


__version__ = "0.1.0"


# Minimal MCP server over stdio (JSON-RPC).
#
# This mirrors the approach we used for peridot-mcp: keep dependencies at zero.

JSON = dict[str, Any]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: JSON


DEFAULT_LEGALIZE_BASE_URL = "https://legalize.dev"


def _base_url() -> str:
    # Useful for tests/self-hosted deployments.
    return os.environ.get("LEGALIZE_BASE_URL", DEFAULT_LEGALIZE_BASE_URL).rstrip("/")


def _build_url(path: str, query: dict[str, Any] | None = None) -> str:
    base = _base_url() + "/"
    url = urllib.parse.urljoin(base, path.lstrip("/"))
    if query:
        qs = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None}, doseq=True)
        if qs:
            url = url + "?" + qs
    return url


def _jsonrpc_result(id_: Any, result: Any) -> JSON:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _jsonrpc_error(id_: Any, code: int, message: str, data: Any | None = None) -> JSON:
    err: JSON = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id_, "error": err}


class OperationalError(RuntimeError):
    """A recoverable / user-facing error (missing key, upstream HTTP errors, network issues)."""

    def __init__(self, message: str, *, data: Any | None = None):
        super().__init__(message)
        self.data = data


def _readline() -> str | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return line


def _write(obj: JSON) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _api_key() -> str:
    key = os.environ.get("LEGALIZE_API_KEY", "").strip()
    if not key:
        raise OperationalError("Missing LEGALIZE_API_KEY env var")
    return key


def _auth_header_value() -> str:
    """Legalize.dev expects: Authorization: Bearer leg_xxx

    We accept either a raw `leg_...` token or a full `Bearer ...` value.
    """

    key = _api_key()
    if key.lower().startswith("bearer "):
        return key
    return f"Bearer {key}"


def _http_get_json(path: str, query: dict[str, Any] | None = None) -> Any:
    """GET JSON from Legalize.dev.

    Raises OperationalError with structured data when possible.
    """

    url = _build_url(path, query=query)

    req = urllib.request.Request(url)
    # OpenAPI securitySchemes.ApiKeyAuth:
    #   in: header
    #   name: Authorization
    #   description: Bearer token
    req.add_header("Authorization", _auth_header_value())
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", f"lawyer-mcp/{__version__} (+https://github.com/pugafran/lawyer-mcp)")

    # Lightweight resilience: Legalize can rate-limit (401/429) or have transient upstream errors.
    max_retries = int(os.environ.get("LEGALIZE_HTTP_RETRIES", "2"))
    timeout_s = float(os.environ.get("LEGALIZE_HTTP_TIMEOUT", "30"))

    last_http_error: urllib.error.HTTPError | None = None

    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            last_http_error = e

            # Retry on transient errors.
            if e.code in {429, 502, 503, 504} and attempt < max_retries:
                retry_after = None
                try:
                    retry_after = e.headers.get("Retry-After")
                except Exception:
                    retry_after = None

                if retry_after is not None:
                    try:
                        sleep_s = float(retry_after)
                    except Exception:
                        sleep_s = 2.0
                else:
                    sleep_s = min(2.0**attempt, 10.0)

                time.sleep(sleep_s)
                continue

            body_text = ""
            try:
                body_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""

            body_json: Any | None = None
            if body_text.strip():
                try:
                    body_json = json.loads(body_text)
                except Exception:
                    body_json = None

            # Produce a clean message, and keep a structured payload for callers.
            msg = f"HTTP {e.code} for {url}".strip()
            if isinstance(body_json, dict) and body_json.get("detail"):
                msg = msg + f": {body_json.get('detail')}"
            elif body_text.strip():
                msg = msg + f": {body_text.strip()}"

            raise OperationalError(
                msg,
                data={
                    "status": e.code,
                    "url": url,
                    "body": body_json if body_json is not None else body_text,
                },
            )
        except urllib.error.URLError as e:
            raise OperationalError(f"Network error for {url}: {e}", data={"url": url})

    # Should be unreachable, but keep a guardrail.
    if last_http_error is not None:
        raise OperationalError(f"HTTP {last_http_error.code} for {url}", data={"status": last_http_error.code, "url": url})
    raise OperationalError(f"Request failed for {url}", data={"url": url})


def tool_countries() -> JSON:
    return {"countries": _http_get_json("/api/v1/countries")}


def tool_jurisdictions(country: str) -> JSON:
    return {"country": country, "jurisdictions": _http_get_json(f"/api/v1/{country}/jurisdictions")}


def tool_laws(
    country: str,
    q: str | None = None,
    page: int = 1,
    per_page: int = 50,
    law_type: str | None = None,
    year: int | None = None,
    status: str | None = None,
    jurisdiction: str | None = None,
) -> JSON:
    data = _http_get_json(
        f"/api/v1/{country}/laws",
        query={
            "q": q,
            "page": page,
            "per_page": per_page,
            "law_type": law_type,
            "year": year,
            "status": status,
            "jurisdiction": jurisdiction,
        },
    )
    return {"country": country, "data": data}


def tool_law_meta(country: str, law_id: str) -> JSON:
    return {"country": country, "law_id": law_id, "meta": _http_get_json(f"/api/v1/{country}/laws/{law_id}/meta")}


def tool_law_get(country: str, law_id: str) -> JSON:
    return {"country": country, "law_id": law_id, "law": _http_get_json(f"/api/v1/{country}/laws/{law_id}")}


def tool_reforms(country: str, law_id: str, limit: int = 100, offset: int = 0) -> JSON:
    data = _http_get_json(
        f"/api/v1/{country}/laws/{law_id}/reforms",
        query={"limit": limit, "offset": offset},
    )
    return {"country": country, "law_id": law_id, "data": data}


def tool_commits(country: str, law_id: str) -> JSON:
    data = _http_get_json(f"/api/v1/{country}/laws/{law_id}/commits")
    return {"country": country, "law_id": law_id, "data": data}


def tool_law_at_commit(country: str, law_id: str, sha: str) -> JSON:
    data = _http_get_json(f"/api/v1/{country}/laws/{law_id}/at/{sha}")
    return {"country": country, "law_id": law_id, "sha": sha, "law": data}


def tool_rangos(country: str) -> JSON:
    data = _http_get_json(f"/api/v1/{country}/rangos")
    return {"country": country, "rangos": data}


def tool_stats(country: str, jurisdiction: str | None = None) -> JSON:
    data = _http_get_json(
        f"/api/v1/{country}/stats",
        query={"jurisdiction": jurisdiction},
    )
    return {"country": country, "jurisdiction": jurisdiction, "stats": data}


TOOLS: list[Tool] = [
    Tool(
        name="legalize_countries",
        description="List supported countries.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    Tool(
        name="legalize_jurisdictions",
        description="List jurisdictions within a country.",
        input_schema={
            "type": "object",
            "properties": {"country": {"type": "string"}},
            "required": ["country"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_laws",
        description="Search/list laws within a country.",
        input_schema={
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "q": {"type": "string"},
                "page": {"type": "integer", "default": 1, "minimum": 1},
                "per_page": {"type": "integer", "default": 50, "minimum": 1, "maximum": 100},
                "law_type": {"type": "string"},
                "year": {"type": "integer"},
                "status": {"type": "string"},
                "jurisdiction": {"type": "string"},
            },
            "required": ["country"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_law_at_commit",
        description="Fetch the law content as it was at a specific git commit SHA.",
        input_schema={
            "type": "object",
            "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}, "sha": {"type": "string"}},
            "required": ["country", "law_id", "sha"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_rangos",
        description="List the legal hierarchy/ranks (rangos) for a country.",
        input_schema={
            "type": "object",
            "properties": {"country": {"type": "string"}},
            "required": ["country"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_stats",
        description="Get summary statistics for a country (optionally filtered by jurisdiction).",
        input_schema={
            "type": "object",
            "properties": {"country": {"type": "string"}, "jurisdiction": {"type": "string"}},
            "required": ["country"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_law_meta",
        description="Get metadata for a law (lightweight endpoint).",
        input_schema={
            "type": "object",
            "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}},
            "required": ["country", "law_id"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_law_get",
        description="Fetch a full law payload.",
        input_schema={
            "type": "object",
            "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}},
            "required": ["country", "law_id"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_reforms",
        description="List reforms (diffs) for a law, newest-first; useful for change tracking.",
        input_schema={
            "type": "object",
            "properties": {
                "country": {"type": "string"},
                "law_id": {"type": "string"},
                "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 1000},
                "offset": {"type": "integer", "default": 0, "minimum": 0},
            },
            "required": ["country", "law_id"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="legalize_commits",
        description="List git commits for a law repository (lightweight history).",
        input_schema={
            "type": "object",
            "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}},
            "required": ["country", "law_id"],
            "additionalProperties": False,
        },
    ),
]


def _handle_initialize(_params: JSON) -> JSON:
    return {
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {
            "name": "lawyer-mcp",
            "version": "0.1.0",
            "description": (
                "AI-callable tools for querying Legalize.dev (open legislation as code) to retrieve structured law data by country, "
                "jurisdiction and law id."
            ),
        },
    }


def _handle_tools_list() -> JSON:
    return {
        "tools": [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in TOOLS
        ]
    }


def _handle_tools_call(params: JSON) -> JSON:
    name = params.get("name")
    args = params.get("arguments") or {}

    if name == "legalize_countries":
        payload = tool_countries()
    elif name == "legalize_jurisdictions":
        payload = tool_jurisdictions(str(args["country"]))
    elif name == "legalize_laws":
        payload = tool_laws(
            str(args["country"]),
            q=(str(args["q"]) if args.get("q") is not None else None),
            page=int(args.get("page", 1)),
            per_page=int(args.get("per_page", 50)),
            law_type=(str(args["law_type"]) if args.get("law_type") is not None else None),
            year=(int(args["year"]) if args.get("year") is not None else None),
            status=(str(args["status"]) if args.get("status") is not None else None),
            jurisdiction=(str(args["jurisdiction"]) if args.get("jurisdiction") is not None else None),
        )
    elif name == "legalize_law_at_commit":
        payload = tool_law_at_commit(str(args["country"]), str(args["law_id"]), str(args["sha"]))
    elif name == "legalize_rangos":
        payload = tool_rangos(str(args["country"]))
    elif name == "legalize_stats":
        payload = tool_stats(
            str(args["country"]),
            jurisdiction=(str(args["jurisdiction"]) if args.get("jurisdiction") is not None else None),
        )
    elif name == "legalize_law_meta":
        payload = tool_law_meta(str(args["country"]), str(args["law_id"]))
    elif name == "legalize_law_get":
        payload = tool_law_get(str(args["country"]), str(args["law_id"]))
    elif name == "legalize_reforms":
        payload = tool_reforms(
            str(args["country"]),
            str(args["law_id"]),
            limit=int(args.get("limit", 100)),
            offset=int(args.get("offset", 0)),
        )
    elif name == "legalize_commits":
        payload = tool_commits(str(args["country"]), str(args["law_id"]))
    else:
        raise ValueError(f"Unknown tool: {name}")

    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]}


def main() -> None:
    while True:
        line = _readline()
        if line is None:
            return
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        id_ = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        try:
            if method == "initialize":
                _write(_jsonrpc_result(id_, _handle_initialize(params)))
            elif method == "tools/list":
                _write(_jsonrpc_result(id_, _handle_tools_list()))
            elif method == "tools/call":
                _write(_jsonrpc_result(id_, _handle_tools_call(params)))
            else:
                _write(_jsonrpc_error(id_, -32601, f"Method not found: {method}"))
        except (KeyError, ValueError, TypeError) as exc:
            # Invalid params / unknown tool name / type coercion failures.
            _write(
                _jsonrpc_error(
                    id_,
                    -32602,
                    f"Invalid params: {exc}",
                    data={"traceback": traceback.format_exc()},
                )
            )
        except OperationalError as exc:
            # Operational errors (missing API key, upstream HTTP errors, network issues).
            _write(
                _jsonrpc_error(
                    id_,
                    -32000,
                    str(exc),
                    data=getattr(exc, "data", None),
                )
            )
        except Exception as exc:
            _write(
                _jsonrpc_error(
                    id_,
                    -32603,
                    f"Internal error: {exc}",
                    data={"traceback": traceback.format_exc()},
                )
            )


if __name__ == "__main__":
    main()
