import json
import os
import subprocess
import sys
import unittest


def send(proc: subprocess.Popen, msg: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None

    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()

    line = proc.stdout.readline().decode("utf-8")
    assert line
    return json.loads(line)


class TestErrors(unittest.TestCase):
    def test_tools_call_unknown_tool_is_invalid_params(self):
        proc = subprocess.Popen(
            [sys.executable, "-m", "lawyer_mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"LEGALIZE_API_KEY": "test"},
        )
        try:
            _ = send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            resp = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "does_not_exist", "arguments": {}},
                },
            )
            self.assertIn("error", resp)
            self.assertEqual(resp["error"]["code"], -32602)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.communicate(timeout=1)
                except Exception:
                    proc.kill()
                    proc.communicate(timeout=1)

    def test_missing_api_key_is_operational_error(self):
        # Ensure the tool call path does not crash the process: should return -32000.
        proc = subprocess.Popen(
            [sys.executable, "-m", "lawyer_mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={},
        )
        try:
            _ = send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            resp = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "legalize_countries", "arguments": {}},
                },
            )
            self.assertIn("error", resp)
            self.assertEqual(resp["error"]["code"], -32000)
            self.assertIn("LEGALIZE_API_KEY", resp["error"]["message"])
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.communicate(timeout=1)
                except Exception:
                    proc.kill()
                    proc.communicate(timeout=1)


if __name__ == "__main__":
    unittest.main()
