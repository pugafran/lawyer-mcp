import os
import unittest
from unittest import mock

import urllib.request

import lawyer_mcp


class TestInvalidJson(unittest.TestCase):
    def setUp(self):
        self._old_key = os.environ.get("LEGALIZE_API_KEY")
        self._old_base = os.environ.get("LEGALIZE_BASE_URL")
        os.environ["LEGALIZE_API_KEY"] = "leg_test"
        os.environ["LEGALIZE_BASE_URL"] = "https://example.test"

    def tearDown(self):
        for k, v in {
            "LEGALIZE_API_KEY": self._old_key,
            "LEGALIZE_BASE_URL": self._old_base,
        }.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_http_get_json_invalid_json_is_operational_error(self):
        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"<html>not json</html>"

        with mock.patch.object(urllib.request, "urlopen", return_value=FakeResp()):
            with self.assertRaises(lawyer_mcp.OperationalError) as ctx:
                lawyer_mcp._http_get_json("/api/v1/countries")

        exc = ctx.exception
        self.assertIn("Invalid JSON response", str(exc))
        self.assertIsInstance(exc.data, dict)
        self.assertIn("body", exc.data)


if __name__ == "__main__":
    unittest.main()
