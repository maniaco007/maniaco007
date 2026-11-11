#!/usr/bin/env python3
"""Testa protect_backups.py: casos que DEVEM bloquear e casos que DEVEM passar."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protect_backups import decide  # noqa: E402


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def tool(name, path):
    return {"tool_name": name, "tool_input": {"file_path": path}}


class TestProtectBackups(unittest.TestCase):
    def test_blocks_writes_to_backups(self):
        for ev in (tool("Edit", "/x/backups/2026_v0/README.md"), tool("Write", "C:\\proj\\backups\\a\\b.txt"),
                   tool("MultiEdit", "backups/a/b"), {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/p/backups/n.ipynb"}},
                   bash("rm -rf backups/2026_x"), bash("sed -i s/a/b/ backups/x/README.md"),
                   bash("echo oi > backups/x/novo.txt"), bash("echo oi >> ./backups/x/novo.txt"),
                   bash("cp a.txt backups/x/"), bash("mv backups/a backups/b"), bash("git checkout -- backups"),
                   bash("git clean -fdx backups"), bash("touch backups/x/y"), bash("tee backups/x/y < a"),
                   bash("chmod -R u+w backups"), bash("truncate -s 0 backups/x/README.md"),
                   bash("scripts/make_backup.sh v1 s r m && rm -rf backups/old"),
                   bash("cd backups/x && rm README.md")):
            self.assertIsNotNone(decide(ev), ev)

    def test_allows_reads_and_normal_work(self):
        for ev in (tool("Edit", "/x/lynx23do/docs/12.md"), tool("Write", "lynx23do/docs/backups_notes.md"),
                   bash("cat backups/x/README.md; ls backups; diff -r a backups/x"), bash("grep -r foo backups | head"),
                   bash("scripts/make_backup.sh v1 slug \"resumo\" \"motivo\""), bash("python3 -m unittest discover"),
                   bash("scripts/check_backups_immutable.sh"), bash("git status --short"),
                   bash("tar -tf backups/x.tar"), {"tool_name": "Read", "tool_input": {"file_path": "backups/x/README.md"}}):
            self.assertIsNone(decide(ev), ev)

    def test_unreadable_event_is_not_blocked(self):
        self.assertIsNone(decide({}))


if __name__ == "__main__":
    unittest.main()
