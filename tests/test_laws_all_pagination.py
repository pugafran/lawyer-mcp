import os
import unittest
from unittest import mock

import urllib.request

import lawyer_mcp


class TestLawsAllPagination(unittest.TestCase):
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

    def test_tool_laws_all_paginates_until_short_page(self):
        # Page 1 -> 100 items, Page 2 -> 2 items (short page), then stop.
        page1 = [{"id": f"law_{i}"} for i in range(100)]
        page2 = [{"id": "law_100"}, {"id": "law_101"}]

        class FakeResp:
            def __init__(self, payload: str):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self._payload.encode("utf-8")

        responses = [
            FakeResp(__import__("json").dumps({"items": page1})),
            FakeResp(__import__("json").dumps({"items": page2})),
        ]

        with mock.patch.object(urllib.request, "urlopen", side_effect=responses) as m_urlopen:
            out = lawyer_mcp.tool_laws_all("es", per_page=100, max_pages=10)

        self.assertEqual(len(out["pages"]), 2)
        self.assertEqual(out["items_count"], 102)
        self.assertEqual(m_urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
