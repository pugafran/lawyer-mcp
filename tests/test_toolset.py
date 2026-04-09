import importlib
import os
import unittest


class TestToolset(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get("LEGALIZE_TOOLSET")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("LEGALIZE_TOOLSET", None)
        else:
            os.environ["LEGALIZE_TOOLSET"] = self._old

    def test_minimal_toolset_hides_nonessential_tools(self):
        os.environ["LEGALIZE_TOOLSET"] = "minimal"

        import lawyer_mcp

        importlib.reload(lawyer_mcp)

        names = {t.name for t in lawyer_mcp.TOOLS}

        # Included
        self.assertIn("legalize_countries", names)
        self.assertIn("legalize_laws", names)
        self.assertIn("legalize_law_meta", names)
        self.assertIn("legalize_reforms", names)

        # Excluded (full-only)
        self.assertNotIn("legalize_account", names)
        self.assertNotIn("legalize_stats", names)
        self.assertNotIn("legalize_rangos", names)
        self.assertNotIn("legalize_law_at_commit", names)


if __name__ == "__main__":
    unittest.main()
