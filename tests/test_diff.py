from pathlib import Path

import pytest

from git_diff import collect_git_diff
from input_parser import InputParser, split_unified_diff
from prompt_engine import PromptEngine
from agent import AgentError

SAMPLE_DIFF = """diff --git a/util.py b/util.py
index 111..222 100644
--- a/util.py
+++ b/util.py
@@ -1,3 +1,3 @@
 def add(x, y):
-    return x - y
+    return x + y
diff --git a/app.py b/app.py
index 333..444 100644
--- a/app.py
+++ b/app.py
@@ -1,4 +1,4 @@
 from util import add
-print(add(2, 2) * 0)
+print(add(2, 2))
diff --git a/photo.png b/photo.png
Binary files /dev/null and b/photo.png differ
"""


def test_split_skips_binary_and_keeps_source_files():
    patches = split_unified_diff(SAMPLE_DIFF)
    names = [item["filename"] for item in patches]
    assert names == ["util.py", "app.py"]


def test_parse_diff_sets_mode_and_mixed_language():
    parsed = InputParser().parse_diff(SAMPLE_DIFF, error="AssertionError", source="git diff HEAD")
    assert parsed["mode"] == "diff"
    assert parsed["error"] == "AssertionError"
    assert parsed["diff_source"] == "git diff HEAD"
    assert [item["filename"] for item in parsed["patches"]] == ["util.py", "app.py"]


def test_parse_files_keeps_cross_file_bundle():
    parsed = InputParser().parse_files(
        [
            ("util.py", "def add(x, y):\n    return x - y\n"),
            ("app.py", "from util import add\nprint(add(2, 2))\n"),
        ]
    )
    assert parsed["mode"] == "files"
    assert len(parsed["files"]) == 2
    assert parsed["language"] == "python"


def test_parse_files_caps_count():
    items = [(f"f{i}.py", f"x = {i}\n") for i in range(InputParser.MAX_FILES + 3)]
    parsed = InputParser().parse_files(items)
    assert len(parsed["files"]) == InputParser.MAX_FILES
    assert any("first" in w for w in parsed["warnings"])


def test_prompt_multi_file_lists_both_paths():
    parsed = InputParser().parse_files(
        [("a.py", "def a():\n    return 1\n"), ("b.py", "from a import a\nprint(a())\n")]
    )
    content = PromptEngine().build(parsed)[0]["content"]
    assert "Mode: multi-file project" in content
    assert "File: a.py" in content
    assert "File: b.py" in content


def test_prompt_diff_includes_hunks():
    content = PromptEngine().build(InputParser().parse_diff(SAMPLE_DIFF))[0]["content"]
    assert "Mode: git / unified diff" in content
    assert "return x - y" in content
    assert "Changed file: app.py" in content


def test_collect_git_diff_rejects_non_repo(tmp_path: Path):
    with pytest.raises(AgentError, match="not a git repository"):
        collect_git_diff(repo=str(tmp_path))
