import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRETTIER = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    / "maya-nvim/mason/bin/prettier"
)


@unittest.skipUnless(
    PRETTIER.is_file() or shutil.which("prettier"), "Prettier required"
)
class MarkdownHookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="maya markdown hook ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Hook test")
        self.git("config", "user.email", "test@example.invalid")
        for name in [".githooks/pre-commit", "scripts/format_markdown.py"]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.git("config", "core.hooksPath", ".githooks")
        binary = self.root / "node_modules/.bin/prettier"
        binary.parent.mkdir(parents=True)
        binary.symlink_to(
            PRETTIER.resolve() if PRETTIER.is_file() else shutil.which("prettier")
        )
        self.prettier = str(binary)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root)

    def formatted(self, name, text):
        return subprocess.check_output(
            [self.prettier, "--stdin-filepath", str(self.root / name)],
            input=text,
            cwd=self.root,
        )

    def test_commit_formats_staged_file_and_worktree(self):
        name = "a file.md"
        raw = b"#Title\n\n|a|b|\n|-|-|\n|x|y|\n"
        (self.root / name).write_bytes(raw)
        self.git("add", "--", name)
        self.git("commit", "-qm", "feat: test staged Markdown")
        expected = self.formatted(name, raw)
        self.assertEqual(self.git("show", "HEAD:" + name), expected)
        self.assertEqual((self.root / name).read_bytes(), expected)
        self.assertEqual(self.git("status", "--porcelain", "--", name), b"")

    def test_partial_stage_preserves_unstaged_edits(self):
        name = "partial.md"
        staged = b"|a|b|\n|-|-|\n|x|y|\n"
        file = self.root / name
        file.write_bytes(staged)
        self.git("add", name)
        working = staged + b"\nDo not commit this unstaged sentence.\n"
        file.write_bytes(working)
        self.git("commit", "-qm", "feat: test partial staging")
        self.assertEqual(self.git("show", "HEAD:" + name), self.formatted(name, staged))
        self.assertEqual(file.read_bytes(), working)
        self.assertNotIn(b"Do not commit", self.git("show", "HEAD:" + name))

    def test_config_ignore_and_unstaged_files_are_respected(self):
        (self.root / ".prettierrc.json").write_text(
            '{"tabWidth":4,"proseWrap":"always","printWidth":30}'
        )
        (self.root / ".prettierignore").write_text("ignored.md\n")
        raw = b"This paragraph is long enough to wrap according to project configuration.\n"
        (self.root / "configured.md").write_bytes(raw)
        (self.root / "ignored.md").write_bytes(raw)
        (self.root / "unstaged.md").write_bytes(raw)
        self.git("add", "configured.md", "ignored.md")
        self.git("commit", "-qm", "feat: test formatter settings")
        self.assertEqual(
            self.git("show", "HEAD:configured.md"), self.formatted("configured.md", raw)
        )
        self.assertEqual(self.git("show", "HEAD:ignored.md"), raw)
        self.assertEqual((self.root / "unstaged.md").read_bytes(), raw)

    def test_python_format_and_partial_stage(self):
        ruff = shutil.which("ruff") or str(PRETTIER.parent / "ruff")
        if not shutil.which(ruff):
            self.skipTest("Ruff required")
        for partial in (False, True):
            name = f"python_{partial}.py"
            raw = b"value={'a':1,'b':2}\n"
            file = self.root / name
            file.write_bytes(raw)
            self.git("add", name)
            working = raw + b"# keep unstaged\n" if partial else raw
            file.write_bytes(working)
            expected = subprocess.check_output(
                [ruff, "format", "--stdin-filename", name], input=raw
            )
            self.git("commit", "-qm", "feat: format Python")
            self.assertEqual(self.git("show", "HEAD:" + name), expected)
            self.assertEqual(file.read_bytes(), working if partial else expected)

    def test_deleted_markdown_does_not_block_commit(self):
        file = self.root / "delete.md"
        file.write_text("# Delete\n")
        self.git("add", "delete.md")
        self.git("commit", "-qm", "feat: add fixture")
        file.unlink()
        self.git("add", "delete.md")
        self.git("commit", "-qm", "fix: remove fixture")
        self.assertEqual(
            self.git(
                "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"
            ).strip(),
            b"D\tdelete.md",
        )


if __name__ == "__main__":
    unittest.main()
