from main import build_arg_parser, main


def test_arg_parser_file_and_error():
    args = build_arg_parser().parse_args(["demo.py", "-e", "TypeError"])
    assert args.file == "demo.py"
    assert args.error == "TypeError"


def test_missing_file_returns_error(tmp_path):
    missing = tmp_path / "nope.py"
    assert main([str(missing)]) == 1
