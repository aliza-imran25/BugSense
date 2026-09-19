from code_compare import (
    diff_rows,
    extract_corrected_files,
    pair_sources,
    reconstruct_patch_sides,
    unified_color_lines,
)
from input_parser import InputParser, chunk_by_top_level, redact_secrets


def test_extracts_fenced_file_under_heading():
    section = """
### app.py
```python
print(2)
```
"""
    files = extract_corrected_files(section)
    assert files == [("app.py", "print(2)")]


def test_extracts_plain_fence():
    files = extract_corrected_files("```python\nx = 1\n```")
    assert files == [("", "x = 1")]


def test_diff_rows_marks_add_and_delete():
    rows = diff_rows("a\nb\nc\n", "a\nB\nc\n")
    kinds = [row[0] for row in rows]
    assert "chg" in kinds or ("del" in kinds and "add" in kinds)


def test_pair_snippet_uses_original_and_corrected():
    parsed = InputParser().parse("print(1)\n", filename="s.py")
    pairs = pair_sources(parsed, "```python\nprint(2)\n```")
    assert len(pairs) == 1
    assert pairs[0][1] == "print(1)"
    assert pairs[0][2] == "print(2)"


def test_pair_files_matches_by_name():
    parsed = InputParser().parse_files(
        [("a.py", "x = 1\n"), ("b.py", "y = 1\n")]
    )
    section = """
### a.py
```python
x = 2
```
### b.py
```python
y = 2
```
"""
    pairs = pair_sources(parsed, section)
    by_name = {name: (old, new) for name, old, new in pairs}
    assert by_name["a.py"] == ("x = 1", "x = 2")
    assert by_name["b.py"] == ("y = 1", "y = 2")


def test_reconstruct_patch_sides():
    patch = """@@ -1,3 +1,3 @@
 def add(x, y):
-    return x - y
+    return x + y
"""
    old, new = reconstruct_patch_sides(patch)
    assert "x - y" in old
    assert "x + y" in new


def test_unified_color_contains_markers():
    text = unified_color_lines("a\n", "b\n")
    assert "- a" in text
    assert "+ b" in text


def test_redacts_api_key():
    warnings: list[str] = []
    out = redact_secrets('API_KEY="sk-abcdefghijklmnopqrstuvwxyz"\n', warnings)
    assert "***REDACTED***" in out
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in out
    assert warnings


def test_sql_detected_from_hints():
    parsed = InputParser().parse("SELECT id FROM users;\n")
    assert parsed["language"] == "sql"


def test_go_extension_wins():
    parsed = InputParser().parse("package main\nfunc main() {}\n", filename="main.go")
    assert parsed["language"] == "go"


def test_truncates_past_new_limit():
    code = "\n".join(f"x = {i}" for i in range(InputParser.MAX_LINES + 40))
    parsed = InputParser().parse(code)
    assert parsed["lines"] == InputParser.MAX_LINES
    assert any("Truncated" in w for w in parsed["warnings"])


def test_chunks_large_multi_function_file():
    parts = []
    for n in range(6):
        parts.append(f"def f{n}():\n" + "\n".join(f"    x = {i}" for i in range(90)))
    code = "\n".join(parts)
    chunks = chunk_by_top_level(code, 100)
    assert len(chunks) > 1
    parsed = InputParser().parse(code, filename="big.py")
    assert parsed["mode"] == "files"
    assert any("split" in w for w in parsed["warnings"])
