import json
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


class TestMcpContract(unittest.TestCase):
    def test_initialize_and_tools_list(self):
        proc = subprocess.Popen(
            [sys.executable, "-m", "lawyer_mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"LEGALIZE_API_KEY": "test"},
        )
        try:
            resp = send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            self.assertEqual(resp["result"]["serverInfo"]["name"], "lawyer-mcp")

            tools = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            names = {t["name"] for t in tools["result"]["tools"]}

            self.assertIn("legalize_countries", names)
            self.assertIn("legalize_law_meta", names)
            self.assertIn("legalize_reforms", names)
            self.assertIn("legalize_commits", names)
            self.assertIn("legalize_law_at_commit", names)
            self.assertIn("legalize_rangos", names)
            self.assertIn("legalize_stats", names)
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
