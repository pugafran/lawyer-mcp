import unittest

import lawyer_mcp


class TestSchemaAnyOfNull(unittest.TestCase):
    def test_anyof_string_null_accepts_none(self):
        tool = next(t for t in lawyer_mcp.TOOLS if t.name == "legalize_laws")
        schema = tool.input_schema

        out = lawyer_mcp._validate_args(schema, {"country": "es", "law_type": None})
        self.assertIn("law_type", out)
        self.assertIsNone(out["law_type"])

    def test_anyof_integer_null_coerces_string(self):
        tool = next(t for t in lawyer_mcp.TOOLS if t.name == "legalize_laws")
        schema = tool.input_schema

        out = lawyer_mcp._validate_args(schema, {"country": "es", "year": "2020"})
        self.assertEqual(out["year"], 2020)


if __name__ == "__main__":
    unittest.main()
