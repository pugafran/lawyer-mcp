import json
import subprocess
import sys


def send(proc: subprocess.Popen, msg: dict) -> dict:
    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()
    line = proc.stdout.readline().decode("utf-8")
    assert line
    return json.loads(line)


def test_initialize_and_tools_list():
    proc = subprocess.Popen(
        [sys.executable, "-m", "lawyer_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"LEGALIZE_API_KEY": "test"},
    )
    try:
        resp = send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert resp["result"]["serverInfo"]["name"] == "lawyer-mcp"

        tools = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in tools["result"]["tools"]}
        assert "legalize_countries" in names
        assert "legalize_law_meta" in names
    finally:
        proc.kill()
