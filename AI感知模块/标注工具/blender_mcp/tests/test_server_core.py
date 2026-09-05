from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


SERVER_PATH = Path(__file__).resolve().parents[1] / "server.py"


def _load_server():
    sys.path.insert(0, str(SERVER_PATH.parent))
    spec = importlib.util.spec_from_file_location("acupoint_mcp_server_test", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ServerCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault(
            "ACUPOINT_MCP_PROJECT_ROOT",
            str(SERVER_PATH.parents[2]),
        )
        cls.server = _load_server()

    def test_project_root_is_ai_module(self):
        self.assertEqual(self.server.PROJECT_ROOT.name, "AI感知模块")

    def test_read_path_rejects_outside_project(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            outside = Path(handle.name)
        try:
            with self.assertRaises(ValueError):
                self.server.checked_read_file(str(outside), {".json"})
        finally:
            outside.unlink(missing_ok=True)

    def test_output_directory_is_unique_and_scoped(self):
        first = self.server._allocate_output_dir("单元测试")
        second = self.server._allocate_output_dir("单元测试")
        self.assertNotEqual(first, second)
        self.assertTrue(self.server._inside(first, self.server.WRITE_ROOT))
        self.assertTrue(self.server._inside(second, self.server.WRITE_ROOT))

    def test_sha256(self):
        target = self.server.WRITE_ROOT / "hash_test.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"ok": True}), encoding="utf-8")
        self.assertEqual(len(self.server._sha256(target)), 64)
        target.unlink()


if __name__ == "__main__":
    unittest.main()
