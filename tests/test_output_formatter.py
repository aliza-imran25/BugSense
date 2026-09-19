from output_formatter import OutputFormatter

SAMPLE = """
[Bug Type]
off-by-one

[Root Cause]
The loop uses <= n so index n is read.

[Corrected Code]
```python
for i in range(n):  # was range(n + 1)
    print(items[i])
```
"""


def test_parses_canonical_sections():
    sections = OutputFormatter().parse_sections(SAMPLE)
    assert sections["Bug Type"] == "off-by-one"
    assert "loop uses" in sections["Root Cause"]
    assert "range(n)" in sections["Corrected Code"]


def test_ignores_brackets_inside_code():
    raw = """
[Bug Type]
logic

[Root Cause]
items[i] is wrong

[Corrected Code]
value = items[i]
"""
    sections = OutputFormatter().parse_sections(raw)
    assert sections["Bug Type"] == "logic"
    assert sections["Corrected Code"] == "value = items[i]"


def test_markdown_falls_back_when_unstructured():
    raw = "just a free-form answer"
    assert OutputFormatter().to_markdown(raw) == raw
