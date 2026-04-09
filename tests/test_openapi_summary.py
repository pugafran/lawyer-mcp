import unittest
from unittest import mock

import urllib.request

import lawyer_mcp


class TestOpenApiSummary(unittest.TestCase):
    def test_openapi_summary_is_public_and_parses(self):
        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"info":{"title":"Legalize API","version":"1.0.0"},"paths":{"/api/v1/countries":{"get":{}},"/pricing":{"get":{}}}}'

        with mock.patch.object(urllib.request, "urlopen", return_value=FakeResp()):
            out = lawyer_mcp.tool_openapi_summary()

        self.assertEqual(out["openapi"]["title"], "Legalize API")
        self.assertIn("/api/v1/countries", out["openapi"]["api_paths"])
        self.assertNotIn("/pricing", out["openapi"]["api_paths"])


if __name__ == "__main__":
    unittest.main()
