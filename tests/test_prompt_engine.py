from prompt_engine import PromptEngine


def test_build_includes_error_and_filename():
    prompt = PromptEngine().build(
        {
            "language": "python",
            "code": "print(1)",
            "error": "NameError",
            "filename": "app.py",
        }
    )
    content = prompt[0]["content"]
    assert "Filename: app.py" in content
    assert "NameError" in content
    assert "print(1)" in content


def test_unknown_language_note():
    content = PromptEngine().build(
        {"language": "unknown", "code": "foo", "error": "", "filename": ""}
    )[0]["content"]
    assert "could not be detected" in content
