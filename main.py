import argparse
import sys
from pathlib import Path

from agent import AgentError, BugSenseAgent
from code_compare import pair_sources, unified_color_lines
from git_diff import collect_git_diff
from input_parser import InputParser
from output_formatter import OutputFormatter


def _read_until_end(prompt: str) -> str:
    print(prompt)
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
        "files",
        nargs="*",
        help="Source files. Two or more are analyzed together as one project.",
    )
    parser.add_argument(
        "-e",
        "--error",
        default="",
        help="Optional compiler/runtime error message.",
    )
    parser.add_argument(
        "--per-file",
        action="store_true",
        help="Analyze each file separately instead of as one project.",
    )
    parser.add_argument(
        "--diff",
        nargs="?",
        const="HEAD",
        metavar="REV",
        help="Analyze git diff vs REV (default HEAD). Use with --staged for the index.",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="With --diff, use git diff --cached.",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Git repository root for --diff (default: current directory).",
    )
    parser.add_argument(
        "--patch",
        help="Path to a unified diff file. Omit to paste a patch when --diff is not used.",
    )
    return parser


def _prompt_error_if_needed(args) -> None:
    if args.error:
        return
    if args.files or args.diff is not None or args.patch:
        return
    try:
        args.error = input("\nError message (press Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        args.error = ""


def _analyze(parsed: dict) -> int:
    agent = BugSenseAgent()
    renderer = OutputFormatter()
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
    pairs = pair_sources(parsed, renderer.parse_sections(response).get("Corrected Code") or "")
    for label, original, corrected in pairs:
        print("\n── Compare (red = removed, green = added) ──")
        if label:
            print(f"{label}")
        print(unified_color_lines(original, corrected))
    return 0


def _read_source_files(paths: list[str]) -> list[tuple[str, str]] | int:
    items: list[tuple[str, str]] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            return 1
        items.append(
            (
                str(path),
                path.read_text(encoding="utf-8", errors="replace"),
            )
        )
    return items


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    print("\n🐛  BugSense — AI Bug Analyst\n")
    parser = InputParser()

    try:
        if args.diff is not None or args.staged:
            patch_text, source = collect_git_diff(
                repo=args.repo,
                revision=args.diff or "HEAD",
                staged=args.staged,
                pathspecs=args.files or None,
            )
            if not patch_text.strip():
                print("No diff to analyze (working tree matches the revision).", file=sys.stderr)
                return 1
            parsed = parser.parse_diff(patch_text, args.error, source=source)
            return _analyze(parsed)

        if args.patch:
            path = Path(args.patch)
            if not path.is_file():
                print(f"File not found: {path}", file=sys.stderr)
                return 1
            patch_text = path.read_text(encoding="utf-8", errors="replace")
            parsed = parser.parse_diff(patch_text, args.error, source=str(path))
            return _analyze(parsed)

        if args.files:
            loaded = _read_source_files(args.files)
            if loaded == 1:
                return 1
            if args.per_file or len(loaded) == 1:
                exit_code = 0
                for filename, code in loaded:
                    if len(loaded) > 1:
                        print(f"\n=== {filename} ===\n")
                    parsed = parser.parse(code, args.error, filename=filename)
                    if not parsed["code"].strip():
                        print(f"No code in {filename}.", file=sys.stderr)
                        exit_code = 1
                        continue
                    result = _analyze(parsed)
                    if result != 0:
                        return result
                return exit_code
            parsed = parser.parse_files(loaded, args.error)
            if not parsed["files"]:
                print("No code provided.", file=sys.stderr)
                return 1
            return _analyze(parsed)

        try:
            if sys.stdin.isatty():
                hint = input("Paste mode [code/diff] (default code): ").strip().lower()
            else:
                hint = "code"
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 130

        try:
            if hint in {"diff", "patch", "d"}:
                pasted = _read_until_end(
                    "Paste a unified diff. Type END on a new line when done.\n"
                )
            else:
                pasted = _read_until_end(
                    "Paste your code below. Type END on a new line when done.\n"
                )
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 130

        _prompt_error_if_needed(args)
        if not pasted.strip():
            print("No code provided.", file=sys.stderr)
            return 1
        if hint in {"diff", "patch", "d"}:
            parsed = parser.parse_diff(pasted, args.error, source="pasted diff")
        else:
            parsed = parser.parse(pasted, args.error)
        return _analyze(parsed)
    except AgentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
