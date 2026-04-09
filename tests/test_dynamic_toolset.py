import os
import unittest

import lawyer_mcp


class TestDynamicToolset(unittest.TestCase):
    def setUp(self):
        self._old_toolset = os.environ.get("LEGALIZE_TOOLSET")
        self._old_danger = os.environ.get("LEGALIZE_ENABLE_DANGEROUS_TOOLS")

    def tearDown(self):
        if self._old_toolset is None:
            os.environ.pop("LEGALIZE_TOOLSET", None)
        else:
            os.environ["LEGALIZE_TOOLSET"] = self._old_toolset

        if self._old_danger is None:
            os.environ.pop("LEGALIZE_ENABLE_DANGEROUS_TOOLS", None)
        else:
            os.environ["LEGALIZE_ENABLE_DANGEROUS_TOOLS"] = self._old_danger

    def test_current_tools_reacts_to_env_changes(self):
        os.environ["LEGALIZE_TOOLSET"] = "full"
        os.environ.pop("LEGALIZE_ENABLE_DANGEROUS_TOOLS", None)
        full_names = {t.name for t in lawyer_mcp._current_tools()}
        self.assertIn("legalize_account", full_names)
        self.assertNotIn("legalize_rotate_key", full_names)

        os.environ["LEGALIZE_TOOLSET"] = "minimal"
        minimal_names = {t.name for t in lawyer_mcp._current_tools()}
        self.assertIn("legalize_laws", minimal_names)
        self.assertNotIn("legalize_account", minimal_names)

        os.environ["LEGALIZE_ENABLE_DANGEROUS_TOOLS"] = "1"
        danger_names = {t.name for t in lawyer_mcp._current_tools()}
        self.assertIn("legalize_rotate_key", danger_names)


if __name__ == "__main__":
    unittest.main()
