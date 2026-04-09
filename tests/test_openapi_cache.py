import os
import unittest
from unittest import mock

import urllib.request

import lawyer_mcp


class TestOpenApiCache(unittest.TestCase):
    def setUp(self):
        self._old_ttl = os.environ.get("LEGALIZE_OPENAPI_TTL")

        # Ensure a clean cache per test.
        lawyer_mcp._OPENAPI_CACHE = None

    def tearDown(self):
        if self._old_ttl is None:
            os.environ.pop("LEGALIZE_OPENAPI_TTL", None)
        else:
            os.environ["LEGALIZE_OPENAPI_TTL"] = self._old_ttl

        lawyer_mcp._OPENAPI_CACHE = None

    def test_openapi_summary_uses_cache_within_ttl(self):
        os.environ["LEGALIZE_OPENAPI_TTL"] = "60"

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"info":{"title":"Legalize API","version":"1.0.0"},"paths":{}}'

        with mock.patch.object(urllib.request, "urlopen", return_value=FakeResp()) as m_urlopen:
            _ = lawyer_mcp.tool_openapi_summary()
            _ = lawyer_mcp.tool_openapi_summary()

        # Should only fetch once.
        self.assertEqual(m_urlopen.call_count, 1)

    def test_openapi_summary_cache_can_be_disabled(self):
        os.environ["LEGALIZE_OPENAPI_TTL"] = "0"

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"info":{"title":"Legalize API","version":"1.0.0"},"paths":{}}'

        with mock.patch.object(urllib.request, "urlopen", return_value=FakeResp()) as m_urlopen:
            _ = lawyer_mcp.tool_openapi_summary()
            _ = lawyer_mcp.tool_openapi_summary()

        # No caching -> called twice.
        self.assertEqual(m_urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
