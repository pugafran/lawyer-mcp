import os
import unittest

import lawyer_mcp


class TestAuthHeader(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("LEGALIZE_API_KEY")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("LEGALIZE_API_KEY", None)
        else:
            os.environ["LEGALIZE_API_KEY"] = self._old

    def test_adds_bearer_prefix_when_missing(self):
        os.environ["LEGALIZE_API_KEY"] = "leg_123"
        self.assertEqual(lawyer_mcp._auth_header_value(), "Bearer leg_123")

    def test_keeps_bearer_prefix_when_present(self):
        os.environ["LEGALIZE_API_KEY"] = "Bearer leg_456"
        self.assertEqual(lawyer_mcp._auth_header_value(), "Bearer leg_456")


if __name__ == "__main__":
    unittest.main()
