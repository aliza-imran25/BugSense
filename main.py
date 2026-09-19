import argparse
import sys
from pathlib import Path

from agent import AgentError, BugSenseAgent
from input_parser import InputParser
from output_formatter import OutputFormatter


def _read_pasted_code() -> str:
    print("Paste your code below. Type END on a new line when done.\n")
    lines: list[str] = []
    try:
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BugSense — AI Bug Analyst")
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a source file. If omitted, paste code and finish with END.",
    )
    parser.add_argument(
        "-e",
        "--error",
        default="",
        help="Optional compiler/runtime error message.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    filename = ""
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            return 1
        code_input = path.read_text(encoding="utf-8", errors="replace")
        filename = path.name
        print("\n🐛  BugSense — AI Bug Analyst\n")
    else:
        print("\n🐛  BugSense — AI Bug Analyst\n")
        try:
            code_input = _read_pasted_code()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 130

        if args.error:
            error_msg = args.error
        else:
            try:
                error_msg = input("\nError message (press Enter to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                error_msg = ""
        args.error = error_msg

    if not code_input.strip():
        print("No code provided.", file=sys.stderr)
        return 1

    parser = InputParser()
    agent = BugSenseAgent()
    renderer = OutputFormatter()
    parsed = parser.parse(code_input, args.error, filename=filename)

    for warning in parsed["warnings"]:
        print(f"[warn] {warning}", file=sys.stderr)

    try:
        response = agent.analyze(parsed)
    except AgentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130

    renderer.display(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
