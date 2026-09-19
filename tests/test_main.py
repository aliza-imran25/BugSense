from main import build_arg_parser, main


def test_arg_parser_file_and_error():
    args = build_arg_parser().parse_args(["demo.py", "-e", "TypeError"])
    assert args.files == ["demo.py"]
    assert args.error == "TypeError"


def test_arg_parser_multi_file_and_diff():
    args = build_arg_parser().parse_args(["a.py", "b.py", "--diff", "main"])
    assert args.files == ["a.py", "b.py"]
    assert args.diff == "main"


def test_missing_file_returns_error(tmp_path):
    missing = tmp_path / "nope.py"
    assert main([str(missing)]) == 1


def test_missing_patch_file_returns_error(tmp_path):
    missing = tmp_path / "nope.diff"
    assert main(["--patch", str(missing)]) == 1
