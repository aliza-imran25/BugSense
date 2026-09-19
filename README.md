# BugSense

BugSense is a small debugging companion for students and developers. It sends a snippet, a set of project files, or a git diff to Gemini and returns:

- **Bug Type** — category of the problem, or `None` if the code looks fine
- **Root Cause** — a step-by-step explanation (including cross-file causes)
- **Corrected Code** — a fix with comments; multi-file/diff results are labeled by path

Submitted code is sent to Google. This is not a local static analyzer.

## API key (required)

1. Create a key at [Google AI Studio](https://aistudio.google.com/apikey).
2. In the **project root** (same folder as `streamlit_app.py` and `main.py`):

```bash
cp .env.example .env
```

3. Open `.env` and replace the placeholder:

```
GEMINI_API_KEY=paste_your_key_here
```

Do not commit `.env`. Optional: set `GEMINI_MODEL` in the same file. Restart Streamlit after changing the key.

## Setup

```bash
git clone https://github.com/aliza-imran25/BugSense.git
cd BugSense
uv sync --group dev
cp .env.example .env
```

## Usage

Web UI:

```bash
uv run streamlit run streamlit_app.py
```

- **Paste Code** — one snippet
- **Multi-file** — upload several files or a folder; leave “Analyze together” on to catch caller/callee bugs
- **Diff** — paste/upload a unified patch, or run `git diff` against a local repo path

CLI — one file:

```bash
uv run python main.py path/to/buggy.py -e "TypeError: ..."
```

CLI — several files together (cross-file analysis):

```bash
uv run python main.py src/util.py src/app.py -e "AssertionError"
uv run python main.py --per-file src/util.py src/app.py
```

CLI — git diff (real-bug workflow):

```bash
uv run python main.py --diff
uv run python main.py --diff main --repo /path/to/project
uv run python main.py --diff --staged
uv run python main.py --patch changes.diff
```

Snippets are capped at 100 lines per file (400 lines total for a bundle, 500 for a diff, 12 files).

## Project layout

| File | Role |
| --- | --- |
| `streamlit_app.py` | Web UI (snippet, multi-file, diff) |
| `main.py` | Command-line entry point |
| `agent.py` | Gemini client, retries, API key checks |
| `prompt_engine.py` | System and user prompt templates |
| `input_parser.py` | Language detection, bundles, unified diffs |
| `git_diff.py` | Collects `git diff` from a local repo |
| `output_formatter.py` | Parses `[Bug Type]` / `[Root Cause]` / `[Corrected Code]` |

## Tests

```bash
uv run pytest
```

## License

MIT. See [LICENSE](LICENSE).
