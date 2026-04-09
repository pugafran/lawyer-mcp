import io
import os
import unittest
from unittest import mock

import urllib.error
import urllib.request

import lawyer_mcp


class TestHttpClient(unittest.TestCase):
    def setUp(self):
        self._old_key = os.environ.get("LEGALIZE_API_KEY")
        self._old_base = os.environ.get("LEGALIZE_BASE_URL")
        self._old_retries = os.environ.get("LEGALIZE_HTTP_RETRIES")

        os.environ["LEGALIZE_API_KEY"] = "leg_test"

    def tearDown(self):
        for k, v in {
            "LEGALIZE_API_KEY": self._old_key,
            "LEGALIZE_BASE_URL": self._old_base,
            "LEGALIZE_HTTP_RETRIES": self._old_retries,
        }.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_build_url_uses_env_base(self):
        os.environ["LEGALIZE_BASE_URL"] = "https://example.test"
        url = lawyer_mcp._build_url("/api/v1/es/laws", query={"page": 2, "q": "hola"})
        self.assertEqual(url, "https://example.test/api/v1/es/laws?page=2&q=hola")

    def test_http_get_json_retries_on_429(self):
        os.environ["LEGALIZE_BASE_URL"] = "https://example.test"
        os.environ["LEGALIZE_HTTP_RETRIES"] = "1"

        # First call: 429 with Retry-After; second call: returns JSON.
        http_err = urllib.error.HTTPError(
            url="https://example.test/api/v1/countries",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "0"},
            fp=io.BytesIO(b"{\"detail\":\"rate limited\"}"),
        )

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{\"ok\": true}"

        with mock.patch.object(urllib.request, "urlopen", side_effect=[http_err, FakeResp()]) as m_urlopen:
            with mock.patch.object(lawyer_mcp.time, "sleep") as m_sleep:
                out = lawyer_mcp._http_get_json("/api/v1/countries")

        self.assertEqual(out, {"ok": True})
        self.assertEqual(m_urlopen.call_count, 2)
        m_sleep.assert_called()  # uses Retry-After=0 but still called


if __name__ == "__main__":
    unittest.main()
