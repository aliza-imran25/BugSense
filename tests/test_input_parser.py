from input_parser import InputParser


def test_detects_python_from_hints():
    parsed = InputParser().parse("def foo():\n    print('hi')\n")
    assert parsed["language"] == "python"
    assert parsed["warnings"] == []


def test_filename_extension_wins_over_hints():
    parsed = InputParser().parse(
        "int main() { printf(\"hi\"); }",
        filename="Main.java",
    )
    assert parsed["language"] == "java"


def test_unknown_language_without_hints():
    parsed = InputParser().parse("hello world")
    assert parsed["language"] == "unknown"


def test_truncates_long_input_and_records_warning():
    code = "\n".join(f"x = {i}" for i in range(InputParser.MAX_LINES + 50))
    parsed = InputParser().parse(code)
    assert parsed["lines"] == InputParser.MAX_LINES
    assert any("Truncated" in w for w in parsed["warnings"])


def test_strips_error_message():
    parsed = InputParser().parse("print(1)", error="  boom  ")
    assert parsed["error"] == "boom"
