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

# Note: Keep __version__ as the single source of truth (also used in MCP initialize + User-Agent).


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
    """Build an absolute URL to the Legalize API."""

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


@dataclass(frozen=True)
class LegalizeClient:
    base_url: str
    authorization: str
    timeout_s: float = 30.0
    max_retries: int = 2

    @staticmethod
    def from_env() -> "LegalizeClient":
        return LegalizeClient(
            base_url=_base_url(),
            authorization=_auth_header_value(),
            timeout_s=float(os.environ.get("LEGALIZE_HTTP_TIMEOUT", "30")),
            max_retries=int(os.environ.get("LEGALIZE_HTTP_RETRIES", "2")),
        )

    def build_url(self, path: str, query: dict[str, Any] | None = None) -> str:
        base = self.base_url.rstrip("/") + "/"
        url = urllib.parse.urljoin(base, path.lstrip("/"))
        if query:
            qs = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None}, doseq=True)
            if qs:
                url = url + "?" + qs
        return url

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        query: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        """HTTP request returning JSON (or None for empty bodies)."""

        url = self.build_url(path, query=query)

        data_bytes: bytes | None = None
        if body is not None:
            data_bytes = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, method=method.upper(), data=data_bytes)
        req.add_header("Authorization", self.authorization)
        req.add_header("Accept", "application/json")
        if data_bytes is not None:
            req.add_header("Content-Type", "application/json")

        req.add_header("User-Agent", f"lawyer-mcp/{__version__} (+https://github.com/pugafran/lawyer-mcp)")

        last_http_error: urllib.error.HTTPError | None = None

        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    raw = resp.read().decode("utf-8")

                if not raw.strip():
                    return None

                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    snippet = raw.strip()
                    if len(snippet) > 500:
                        snippet = snippet[:500] + "…"
                    raise OperationalError(
                        f"Invalid JSON response for {url}: {e}",
                        data={"url": url, "body": snippet},
                    )
            except urllib.error.HTTPError as e:
                last_http_error = e

                # Retry on transient errors.
                if e.code in {429, 502, 503, 504} and attempt < self.max_retries:
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

        if last_http_error is not None:
            raise OperationalError(
                f"HTTP {last_http_error.code} for {url}",
                data={"status": last_http_error.code, "url": url},
            )
        raise OperationalError(f"Request failed for {url}", data={"url": url})


def _http_request_json(
    path: str,
    *,
    method: str = "GET",
    query: dict[str, Any] | None = None,
    body: Any | None = None,
) -> Any:
    """Backwards-compatible wrapper used by existing tool functions/tests."""

    return LegalizeClient.from_env().request_json(path, method=method, query=query, body=body)


def _http_get_json(path: str, query: dict[str, Any] | None = None) -> Any:
    return _http_request_json(path, method="GET", query=query)


def _http_post_json(path: str, body: Any | None = None) -> Any:
    return _http_request_json(path, method="POST", body=body)


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


def tool_account() -> JSON:
    """Account dashboard JSON: tier, usage, limits, reset date.

    OpenAPI: GET /api/account (Bearer token). Does not count against quota.
    """

    return {"account": _http_get_json("/api/account")}


def _fetch_public_json(url: str, *, timeout_s: float = 30.0) -> Any:
    """Fetch JSON from a public (no-auth) endpoint."""

    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", f"lawyer-mcp/{__version__} (+https://github.com/pugafran/lawyer-mcp)")

    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")

    if not raw.strip():
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        snippet = raw.strip()
        if len(snippet) > 500:
            snippet = snippet[:500] + "…"
        raise OperationalError(
            f"Invalid JSON response for {url}: {e}",
            data={"url": url, "body": snippet},
        )


def tool_openapi_summary() -> JSON:
    """Return a small summary of the Legalize.dev OpenAPI spec.

    This tool is intentionally public (no API key required) and helps agents discover
    available endpoints + required parameters.
    """

    spec = _fetch_public_json(_build_url("/openapi.json"))
    info = (spec or {}).get("info") or {}
    paths = (spec or {}).get("paths") or {}

    api_paths = sorted([p for p in paths.keys() if p.startswith("/api/") or p.startswith("/api/v1/")])

    return {
        "openapi": {
            "title": info.get("title"),
            "version": info.get("version"),
            "total_paths": len(paths),
            "api_paths": api_paths,
        }
    }


def tool_rotate_key() -> JSON:
    """Rotate the caller's API key and return the new one.

    OpenAPI: POST /api/rotate-key (Bearer token). Old key becomes invalid immediately.
    """

    return {"rotated": _http_post_json("/api/rotate-key")}


def _dangerous_tools_enabled() -> bool:
    """Guardrail: disable tools with irreversible side effects by default.

    Set LEGALIZE_ENABLE_DANGEROUS_TOOLS=1 to expose them.
    """

    v = os.environ.get("LEGALIZE_ENABLE_DANGEROUS_TOOLS", "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _toolset() -> str:
    """Choose which MCP tools to expose.

    Env var: LEGALIZE_TOOLSET
      - "full" (default): expose all read-only tools + (optionally) dangerous tools
      - "minimal": expose only the smallest useful subset for typical legal research flows

    Rationale: some MCP hosts prefer very small tool surfaces to reduce model confusion.
    """

    v = os.environ.get("LEGALIZE_TOOLSET", "full").strip().lower()
    if v in {"minimal", "min"}:
        return "minimal"
    return "full"


# --- Tool definitions (shared) ---

TOOL_OPENAPI_SUMMARY = Tool(
    name="legalize_openapi_summary",
    description="Public: summarize the Legalize.dev OpenAPI spec (endpoints, versions). No API key required.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)

TOOL_COUNTRIES = Tool(
    name="legalize_countries",
    description="List supported countries.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)

TOOL_JURISDICTIONS = Tool(
    name="legalize_jurisdictions",
    description="List jurisdictions within a country.",
    input_schema={
        "type": "object",
        "properties": {"country": {"type": "string"}},
        "required": ["country"],
        "additionalProperties": False,
    },
)

TOOL_LAWS = Tool(
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
)

TOOL_LAW_META = Tool(
    name="legalize_law_meta",
    description="Get metadata for a law (lightweight endpoint).",
    input_schema={
        "type": "object",
        "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}},
        "required": ["country", "law_id"],
        "additionalProperties": False,
    },
)

TOOL_LAW_GET = Tool(
    name="legalize_law_get",
    description="Fetch a full law payload.",
    input_schema={
        "type": "object",
        "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}},
        "required": ["country", "law_id"],
        "additionalProperties": False,
    },
)

TOOL_REFORMS = Tool(
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
)

TOOL_COMMITS = Tool(
    name="legalize_commits",
    description="List git commits for a law repository (lightweight history).",
    input_schema={
        "type": "object",
        "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}},
        "required": ["country", "law_id"],
        "additionalProperties": False,
    },
)

TOOL_LAW_AT_COMMIT = Tool(
    name="legalize_law_at_commit",
    description="Fetch the law content as it was at a specific git commit SHA.",
    input_schema={
        "type": "object",
        "properties": {"country": {"type": "string"}, "law_id": {"type": "string"}, "sha": {"type": "string"}},
        "required": ["country", "law_id", "sha"],
        "additionalProperties": False,
    },
)

TOOL_RANGOS = Tool(
    name="legalize_rangos",
    description="List the legal hierarchy/ranks (rangos) for a country.",
    input_schema={
        "type": "object",
        "properties": {"country": {"type": "string"}},
        "required": ["country"],
        "additionalProperties": False,
    },
)

TOOL_STATS = Tool(
    name="legalize_stats",
    description="Get summary statistics for a country (optionally filtered by jurisdiction).",
    input_schema={
        "type": "object",
        "properties": {"country": {"type": "string"}, "jurisdiction": {"type": "string"}},
        "required": ["country"],
        "additionalProperties": False,
    },
)

TOOL_ACCOUNT = Tool(
    name="legalize_account",
    description="Get account usage/limits info for the current API key (does not count against quota).",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)


def _build_tools() -> list[Tool]:
    toolset = _toolset()

    # Minimal, high-signal tool surface.
    minimal: list[Tool] = [
        TOOL_OPENAPI_SUMMARY,
        TOOL_COUNTRIES,
        TOOL_JURISDICTIONS,
        TOOL_LAWS,
        TOOL_LAW_META,
        TOOL_LAW_GET,
        TOOL_REFORMS,
    ]

    full: list[Tool] = minimal + [
        TOOL_COMMITS,
        TOOL_LAW_AT_COMMIT,
        TOOL_RANGOS,
        TOOL_STATS,
        TOOL_ACCOUNT,
    ]

    tools = minimal if toolset == "minimal" else full

    # Opt-in tools with irreversible side effects.
    if _dangerous_tools_enabled():
        tools = tools + [
            Tool(
                name="legalize_rotate_key",
                description="Rotate the current API key and return the new key (shown once).",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            )
        ]

    return tools


TOOLS: list[Tool] = _build_tools()


def _handle_initialize(_params: JSON) -> JSON:
    return {
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {
            "name": "lawyer-mcp",
            "version": __version__,
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


def _tool_by_name(name: str) -> Tool | None:
    for t in TOOLS:
        if t.name == name:
            return t
    return None


def _validate_args(input_schema: JSON, args: Any) -> JSON:
    """Best-effort JSONSchema-ish validation.

    We keep this lightweight (no deps), but still enforce the most useful constraints:
    - required
    - additionalProperties=false
    - type coercion (string/integer/object)
    - integer min/max
    - string enum
    - defaults (when present)
    """

    if not isinstance(args, dict):
        raise TypeError("arguments must be an object")

    props: dict[str, Any] = dict(input_schema.get("properties") or {})
    required: list[str] = list(input_schema.get("required") or [])
    additional = input_schema.get("additionalProperties", True)

    if additional is False:
        unknown = [k for k in args.keys() if k not in props]
        if unknown:
            raise ValueError(f"Unknown argument(s): {', '.join(sorted(unknown))}")

    for k in required:
        if k not in args:
            raise ValueError(f"Missing required argument: {k}")

    out: JSON = {}

    # Apply defaults first (so callers can rely on validated payloads).
    for k, schema in props.items():
        if k not in args and isinstance(schema, dict) and "default" in schema:
            out[k] = schema.get("default")

    for k, v in args.items():
        schema = props.get(k)
        if not schema:
            # allowed only when additionalProperties=True
            out[k] = v
            continue

        t = schema.get("type")
        if t == "string":
            if v is None:
                raise TypeError(f"{k} must be a string")
            sv = str(v)
            enum = schema.get("enum")
            if isinstance(enum, list) and enum and sv not in enum:
                raise ValueError(f"{k} must be one of: {', '.join(map(str, enum))}")
            out[k] = sv
        elif t == "integer":
            if v is None:
                raise TypeError(f"{k} must be an integer")
            try:
                iv = int(v)
            except Exception:
                raise TypeError(f"{k} must be an integer")
            min_v = schema.get("minimum")
            max_v = schema.get("maximum")
            if min_v is not None and iv < int(min_v):
                raise ValueError(f"{k} must be >= {min_v}")
            if max_v is not None and iv > int(max_v):
                raise ValueError(f"{k} must be <= {max_v}")
            out[k] = iv
        elif t == "object":
            if not isinstance(v, dict):
                raise TypeError(f"{k} must be an object")
            out[k] = v
        else:
            # Best-effort passthrough for unsupported schema constructs.
            out[k] = v

    return out


def _handle_tools_call(params: JSON) -> JSON:
    name = str(params.get("name"))
    args_raw = params.get("arguments") or {}

    tool = _tool_by_name(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")

    args = _validate_args(tool.input_schema, args_raw)

    def _opt_str(k: str) -> str | None:
        return str(args[k]) if args.get(k) is not None else None

    def _opt_int(k: str) -> int | None:
        return int(args[k]) if args.get(k) is not None else None

    dispatch: dict[str, Any] = {
        "legalize_openapi_summary": lambda: tool_openapi_summary(),
        "legalize_countries": lambda: tool_countries(),
        "legalize_jurisdictions": lambda: tool_jurisdictions(str(args["country"])),
        "legalize_laws": lambda: tool_laws(
            str(args["country"]),
            q=_opt_str("q"),
            page=int(args.get("page", 1)),
            per_page=int(args.get("per_page", 50)),
            law_type=_opt_str("law_type"),
            year=_opt_int("year"),
            status=_opt_str("status"),
            jurisdiction=_opt_str("jurisdiction"),
        ),
        "legalize_law_at_commit": lambda: tool_law_at_commit(
            str(args["country"]),
            str(args["law_id"]),
            str(args["sha"]),
        ),
        "legalize_rangos": lambda: tool_rangos(str(args["country"])),
        "legalize_stats": lambda: tool_stats(str(args["country"]), jurisdiction=_opt_str("jurisdiction")),
        "legalize_law_meta": lambda: tool_law_meta(str(args["country"]), str(args["law_id"])),
        "legalize_law_get": lambda: tool_law_get(str(args["country"]), str(args["law_id"])),
        "legalize_reforms": lambda: tool_reforms(
            str(args["country"]),
            str(args["law_id"]),
            limit=int(args.get("limit", 100)),
            offset=int(args.get("offset", 0)),
        ),
        "legalize_commits": lambda: tool_commits(str(args["country"]), str(args["law_id"])),
        "legalize_account": lambda: tool_account(),
        "legalize_rotate_key": lambda: tool_rotate_key(),
    }

    fn = dispatch.get(name)
    if fn is None:
        raise ValueError(f"Unknown tool: {name}")

    payload = fn()
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
