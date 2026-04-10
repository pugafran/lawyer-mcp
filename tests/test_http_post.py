import os
import unittest
from unittest import mock

import urllib.request

import lawyer_mcp


class TestHttpPost(unittest.TestCase):
    def setUp(self):
        self._old_key = os.environ.get("LEGALIZE_API_KEY")
        self._old_base = os.environ.get("LEGALIZE_BASE_URL")
        os.environ["LEGALIZE_API_KEY"] = "leg_test"
        os.environ["LEGALIZE_BASE_URL"] = "https://example.test"

    def tearDown(self):
        if self._old_key is None:
            os.environ.pop("LEGALIZE_API_KEY", None)
        else:
            os.environ["LEGALIZE_API_KEY"] = self._old_key

        if self._old_base is None:
            os.environ.pop("LEGALIZE_BASE_URL", None)
        else:
            os.environ["LEGALIZE_BASE_URL"] = self._old_base

    def test_http_post_json_sets_method_post(self):
        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{\"ok\": true}"

        captured = {}

        def fake_urlopen(req: urllib.request.Request, timeout: float = 0, **kwargs):
            _ = kwargs  # accept e.g. SSL context
            captured["method"] = getattr(req, "method", None)
            captured["full_url"] = req.full_url
            return FakeResp()

        with mock.patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            out = lawyer_mcp._http_post_json("/api/rotate-key")

        self.assertEqual(out, {"ok": True})
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["full_url"], "https://example.test/api/rotate-key")


if __name__ == "__main__":
    unittest.main()
