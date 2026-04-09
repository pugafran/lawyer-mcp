import unittest

import lawyer_mcp


class TestSchemaValidation(unittest.TestCase):
    def test_integer_max_is_enforced(self):
        tool = next(t for t in lawyer_mcp.TOOLS if t.name == "legalize_laws")
        schema = tool.input_schema

        with self.assertRaises(ValueError) as ctx:
            lawyer_mcp._validate_args(schema, {"country": "es", "per_page": 101})

        self.assertIn("per_page", str(ctx.exception))
        self.assertIn("<=", str(ctx.exception))

    def test_defaults_are_applied(self):
        tool = next(t for t in lawyer_mcp.TOOLS if t.name == "legalize_laws")
        schema = tool.input_schema

        out = lawyer_mcp._validate_args(schema, {"country": "es"})

        # From the input schema defaults
        self.assertEqual(out["page"], 1)
        self.assertEqual(out["per_page"], 50)


if __name__ == "__main__":
    unittest.main()
