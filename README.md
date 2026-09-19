# BugSense

BugSense is a small debugging companion for students and developers. It sends a code snippet (or uploaded source files) to Gemini and returns three sections:

- **Bug Type** — category of the problem, or `None` if the code looks fine
- **Root Cause** — a step-by-step explanation
- **Corrected Code** — a fix with comments on each change

It is a thin, educational wrapper around the Gemini API, not a local static analyzer. Submitted code is sent to Google.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A [Gemini API key](https://aistudio.google.com/apikey)

## Setup

```bash
git clone https://github.com/aliza-imran25/BugSense.git
cd BugSense
uv sync --group dev
cp .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY`.

## Usage

Web UI:

```bash
uv run streamlit run streamlit_app.py
```

CLI — paste code, then type `END`:

```bash
uv run python main.py
```

CLI — analyze a file:

```bash
uv run python main.py path/to/buggy.py -e "TypeError: ..."
```

The parser keeps the first 100 lines (and at most 200 KB) so prompts stay bounded.

## Project layout

| File | Role |
| --- | --- |
| `streamlit_app.py` | Web UI (paste or upload) |
| `main.py` | Command-line entry point |
| `agent.py` | Gemini client, retries, API key checks |
| `prompt_engine.py` | System and user prompt templates |
| `input_parser.py` | Language detection, truncation, warnings |
| `output_formatter.py` | Parses `[Bug Type]` / `[Root Cause]` / `[Corrected Code]` |

## Tests

```bash
uv run pytest
```

## License

MIT. See [LICENSE](LICENSE).
