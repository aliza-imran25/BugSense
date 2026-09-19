# BugSense code walkthrough

This document explains **every Python module** in the repository: what it does, why it exists, how data moves through it, and how the pieces fit together. Read the [README](README.md) first for setup and usage. This file is the internals guide.

---

## 1. What the system is (and is not)

BugSense is an **LLM application**, not a compiler or static analyzer. It never executes the user’s program. It:

1. Normalizes messy input (snippet, several files, or a unified diff).
2. Builds a **constrained prompt** that forces a three-part answer.
3. Calls **Google Gemini** with retries.
4. Parses the model’s text and **diffs the proposed fix** against the original source.

If Gemini is down, mis-prompted, or invents a bug, BugSense will surface that. The product’s job is to make that failure **visible** (structured sections, side-by-side colors) rather than to guarantee a correct patch.

---

## 2. End-to-end data flow

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌────────────────┐
│ Streamlit / │     │ InputParser  │     │ PromptEngine  │     │ BugSenseAgent  │
│ main.py     │────►│ parse*       │────►│ build()       │────►│ analyze()      │
└─────────────┘     └──────────────┘     └───────────────┘     └───────┬────────┘
       ▲                                                                │
       │            ┌──────────────┐     ┌───────────────┐              │
       └────────────│ code_compare │◄────│ OutputFormat  │◄─────────────┘
                    │ pair + HTML  │     │ parse_sections│   Gemini text
                    └──────────────┘     └───────────────┘
```

Both UIs share the **same pipeline**. They only differ in how they collect bytes and how they render the result.

The parser always returns a **single dictionary** (the “parsed payload”). Downstream code should not care whether the user pasted a snippet or uploaded a folder.

### Parsed payload (canonical shape)

| Key | Meaning |
| --- | --- |
| `mode` | `"snippet"`, `"files"`, or `"diff"` |
| `code` | Combined text sent as a fallback (full snippet, concatenated files, or raw patch) |
| `error` | Optional runtime/compiler message |
| `language` | Detected language, or `"mixed"` / `"unknown"` |
| `filename` | Primary path (first file / first patch) |
| `lines` | Line count after truncation |
| `files` | List of `{filename, language, code, lines}` (snippet/files modes) |
| `patches` | List of `{filename, language, patch, lines}` (diff mode) |
| `diff_source` | Label such as `git diff HEAD (BugSense)` |
| `warnings` | Human-readable notes (truncation, redaction, skipped files) |

---

## 3. `input_parser.py` — turning raw text into a payload

**Why it exists:** Models behave better on *bounded, labeled* input. A 4,000-line dump wastes tokens and hides the bug. This module is the **gate**: language, size, secrets, and structure.

### Language detection

`SOURCE_EXTENSIONS` maps suffixes (`.py`, `.ts`, `.go`, `.sql`, …) to language ids. If there is no filename (paste box), `LANG_HINTS` scans for tokens such as `def `, `public class`, `SELECT `.

**Order matters.** Extension wins over hints so a file named `Main.java` that happens to contain `printf` is still Java. Unknown language is allowed; the prompt then tells Gemini to infer it.

### Size limits (current constants)

| Constant | Default | Role |
| --- | --- | --- |
| `MAX_LINES` | 400 | Per file / snippet |
| `MAX_TOTAL_LINES` | 1600 | Whole multi-file bundle |
| `MAX_FILES` | 20 | Files in a bundle or patch |
| `MAX_DIFF_LINES` | 1500 | Unified diff text |
| `MAX_BYTES` | 500_000 | UTF-8 byte cap before line trim |

Oversized input is **truncated with a warning**, not rejected. The UI shows those warnings so the user knows the model did not see the whole file.

### Secret redaction — `redact_secrets()`

A regex looks for assignments like `api_key=...`, `token: ...`, `password=...`. The value is replaced with `***REDACTED***` **before** the payload is built. This is heuristic, not a security boundary: do not paste production secrets.

Redaction runs inside `_truncate_text()` (and again at the start of `parse()`), so both snippet and multi-file paths are covered.

### Chunking — `chunk_by_top_level()`

If a single file is longer than `MAX_LINES` **and** it has at least two top-level definitions (`def `, `class `, `function `, `func `, `fn `, …), BugSense splits on those boundaries and packs chunks that still fit the line budget.

`parse()` then **promotes** that snippet into `mode: "files"` with names like `app.py#part1`. That way the prompt engine can label each chunk, and the model is less likely to ignore the bottom of a huge paste.

If there are not enough split points, the file is truncated as usual.

### `parse()` — one snippet

Returns `mode: "snippet"` with a one-element `files` list (used later by the diff UI). Empty input yields `files: []`.

### `parse_files()` — project bundle

Takes `list[tuple[path, source]]`. It:

1. Caps file **count**, then remaining **line budget**.
2. Detects language per file.
3. Sets `language` to `"mixed"` when extensions disagree.
4. Builds `code` as a concatenated `# path` document (legacy/fallback text).

This is how **caller/callee bugs** get into one Gemini request instead of N isolated analyses.

### `parse_diff()` and `split_unified_diff()`

Unified diffs are split on `diff --git ` lines. Binary blobs (`Binary files`, `GIT binary patch`) are dropped. Files whose suffix is not in `SOURCE_EXTENSIONS` are skipped (so `package-lock.json` does not consume the budget).

`_filename_from_diff_chunk()` prefers `+++ b/path`, then `--- a/path`, then the `diff --git` header.

---

## 4. `git_diff.py` — talking to a real repository

**Why it exists:** Pasting a patch is awkward. Engineers already have `git diff`.

`collect_git_diff(repo, revision, staged, pathspecs)`:

1. Resolves the path and checks for `.git`.
2. Runs `git -C <root> diff --no-ext-diff --no-color` (never a pager, never ANSI).
3. Uses `--cached` when `staged=True`.
4. Restricts to `SOURCE_GLOBS` (`**/*.py`, `**/*.ts`, …) unless the user passed pathspecs.

Failures become `AgentError` (missing git, not a repo, non-zero git). An **empty** stdout is not an error — it means the tree matches the revision; the UI shows an info message.

This module does **not** parse the patch. Parsing stays in `input_parser.py` so CLI and Streamlit share one implementation.

---

## 5. `prompt_engine.py` — the contract with the model

**Why it exists:** Unconstrained chat yields essays. BugSense needs **machine-parseable** output: three labeled sections and a **full file** in a fence (so `code_compare` can diff line-by-line).

### System prompt (`SYSTEM_PROMPT`)

Tells the model it is a **teacher**, not an auto-fixer:

- Do not invent a bug; use `[Bug Type] None` if the code is fine.
- Always emit `[Bug Type]`, `[Root Cause]`, `[Corrected Code]`.
- Corrected code must be the **entire** updated source, with `### path` headings for multi-file/diff.

### User prompt (`build()`)

Dispatches on `parsed["mode"]`:

| Mode | What the user message contains |
| --- | --- |
| snippet | Language, optional filename, fenced code, optional error |
| files | Explicit “bugs may live across files”, then each path in its own fence |
| diff | Source label + per-file ` ```diff ` hunks |

Every mode ends with the same three-step instruction (type → why → show full fix). Optional error text is injected only when present, so the model is not primed with a blank “Error message:” line.

`build()` returns `[{"role": "user", "content": ...}]`. That list shape is leftover from chat-style APIs. `BugSenseAgent.run()` only reads `prompt_list[0]["content"]` and sends **system_instruction separately** via the Gemini SDK. Keeping the list makes the engine easy to point at another provider later.

---

## 6. `agent.py` — Gemini client, retries, errors

**Why it exists:** Isolate I/O. The rest of the app should not import `google.genai`.

### `AgentError`

A **domain** exception. Streamlit shows `st.error(str(exc))`; the CLI prints to stderr and returns `1`. Transient HTTP failures are retried; auth/empty-prompt problems are not.

### Lazy client

`genai.Client()` is created on first `analyze()`, not at import. That lets the Streamlit page load enough to say “missing API key” without constructing a client.

`api_key_configured()` reloads `.env` and checks `GEMINI_API_KEY`. Model id comes from `GEMINI_MODEL` or defaults to `gemini-3-flash-preview`.

### `analyze(parsed)` vs `run(prompt_list)`

`analyze` is the public method: parse already happened, now build prompt + call the API. `run` is the lower-level hook (useful in tests or if a caller already has a prompt).

### Generation config

`temperature=0.2` — bug classification should be stable, not creative.

System instruction is passed in `GenerateContentConfig`, not concatenated into the user string. That keeps the “you are a teacher” rules from being mixed into the student’s code block.

### Retry policy

Retries **3** times with exponential backoff (`1s, 2s, 4s`) only when `_is_retryable` is true:

- Status codes 408, 429, 500, 502, 503, 504
- Or message tokens: timeout, rate limit, unavailable, connection reset, …

Empty model text is `AgentError` and is **not** retried (it is a contract failure, not a blip). Non-retryable errors (invalid key) fail on the first attempt.

---

## 7. `output_formatter.py` — splitting the model’s essay

Gemini is asked to use `[Bug Type]` / `[Root Cause]` / `[Corrected Code]`. The formatter **enforces** that on the way out.

`_SECTION_RE` is a DOTALL regex that captures those three headings and stops at the next heading. Brackets **inside** the code (e.g. `items[i]`) do not start a new section because the next heading must be one of the three names.

- `parse_sections()` → dict of the three strings  
- `to_markdown()` → GitHub-style `###` headings (unused by the current Streamlit path, kept for reuse)  
- `display()` → ANSI-colored CLI blocks (red / yellow / green)

If **no** section matches, `to_markdown()` returns the raw string so a free-form failure is still visible.

---

## 8. `code_compare.py` — red/green side-by-side

**Why it exists:** A wall of “corrected code” hides what changed. Humans compare **left vs right**.

### Extracting the new source

`extract_corrected_files()`:

1. If the section has `### path` headings, each heading’s body is one file.
2. Otherwise, the first markdown fence is the whole file.
3. `strip_fence()` removes ` ```python ` wrappers.

### Pairing with the original — `pair_sources()`

| Mode | Left column | Right column |
| --- | --- | --- |
| snippet | `parsed["code"]` | Extracted fence |
| files | Each original file, matched by path or basename | Matching `###` block |
| diff | Old side reconstructed from `-` / context lines | Model’s full file (or `+` side if the model returned a patch) |

`reconstruct_patch_sides()` walks a unified hunk: `-` → old only, `+` → new only, ` ` → both. Headers (`diff`, `@@`, `---`) are skipped. This is **hunk context**, not a full historical file — enough to show what the model changed relative to the patch.

### Alignment — `diff_rows()`

`difflib.SequenceMatcher` (no autojunk) emits opcodes: equal, delete, insert, replace. Replace is expanded into per-line `chg` rows so a modified line is **red on the left and green on the right** in the same row.

### Rendering

- `side_by_side_html()` — table with line numbers; `.del` = `#ffd7d5`, `.add` = `#ccffd8`. Streamlit injects this via `st.html`.
- `unified_color_lines()` — same rows as ANSI `-` / `+` for the terminal.

Neither renderer executes code; they only color strings.

---

## 9. `streamlit_app.py` — web UI

Script runs **top to bottom on every interaction** (Streamlit’s model). Heavy objects are cached:

```python
@st.cache_resource
def get_agent() -> BugSenseAgent: ...
```

Parser, formatter, and agent are created once per server process.

### Guard

If `GEMINI_API_KEY` is missing, the page shows an error and `st.stop()` — no tabs, no accidental API calls.

### Three tabs

1. **Paste Code** — `parse()` + Analyze.  
2. **Multi-file** — directory or multi-select; **Analyze together** (default on) calls `parse_files()`; off wraps each file in an expander and calls `parse()` per file.  
3. **Diff** — pasted/uploaded patch, or `collect_git_diff()` from a local path.

`decode_upload()` requires UTF-8; binary uploads get an error instead of a crash.

### `analyze_parsed()` / `render_result()`

Shared by all tabs: empty-input checks → spinner → `agent.analyze` → warnings → sections. Corrected code is **not** dumped as markdown first; it goes through `pair_sources` + HTML. An expander still offers the full file to copy.

Widget `key=` values (`upload_error`, `pasted_diff`, …) prevent Streamlit from colliding two “Error message” boxes across tabs.

---

## 10. `main.py` — CLI

Same pipeline, argparse instead of widgets.

| Invocation | Behavior |
| --- | --- |
| `main.py file.py` | One snippet (`parse`) |
| `main.py a.py b.py` | Together (`parse_files`) |
| `main.py --per-file a.py b.py` | Sequential snippets |
| `main.py --diff [REV]` | `collect_git_diff` |
| `main.py --patch file.diff` | File as unified diff |
| no args, TTY | Interactive paste until a line `END` |

Exit codes: `0` ok, `1` user/API error, `130` Ctrl+C.

After `OutputFormatter.display()`, the CLI prints the colorized compare so a terminal user gets the same “what changed” story as the web UI.

---

## 11. Tests (`tests/`)

| File | What it locks in |
| --- | --- |
| `test_input_parser.py` | Hints vs extension, truncation, unknown language |
| `test_diff.py` | Binary skip, multi-file bundle, prompt contains both paths, git on non-repo |
| `test_code_compare.py` | Fence extraction, pairing, redaction, SQL/Go detection, chunking |
| `test_prompt_engine.py` | Error + filename in the user message |
| `test_output_formatter.py` | Section split; `[i]` inside code is not a heading |
| `test_agent.py` | Retryable timeout vs non-retryable auth |
| `test_main.py` | Argparse and missing-file exit code |

Tests **do not** call Gemini. That keeps CI free and deterministic. `pythonpath = ["."]` in `pyproject.toml` lets tests import top-level modules.

Run: `uv run pytest`.

---

## 12. Configuration and packaging

| File | Role |
| --- | --- |
| `pyproject.toml` | Package name `bugsense`, Python `>=3.12`, deps: `google-genai`, `python-dotenv`, `streamlit`; dev group: `pytest` |
| `.env.example` | `GEMINI_API_KEY`, optional `GEMINI_MODEL` |
| `.env` | Real secrets — gitignored |
| `.python-version` | Pin for `uv` |
| `uv.lock` | Reproducible lockfile |
| `LICENSE` | MIT |

There is no `bugsense.toml` yet; limits live as class attributes on `InputParser`. Changing them in one place updates parser, tests, and (via `MAX_LINES`) the Streamlit help text.

---

## 13. Design choices worth copying (or questioning)

**Copy**

- One parsed dict for all modes.  
- System prompt as a **contract**, not a vibe.  
- Retries only for transient errors.  
- Diff the model’s output against the user’s bytes so mistakes are obvious.

**Question later**

- No eval set: you cannot prove the bug type is right.  
- No sandbox: the suggested fix is never compiled.  
- Chunking can split a bug from its caller.  
- Redaction is regex-only.  
- `gemini-3-flash-preview` is a moving target; pin via `GEMINI_MODEL` when you need reproducibility.

---

## 14. Suggested reading order for newcomers

1. This file, section 2 (flow).  
2. `input_parser.py` (`parse`, `parse_files`, `parse_diff`).  
3. `prompt_engine.py` (system + `_build_*`).  
4. `agent.py` (`analyze` / retry loop).  
5. `output_formatter.py` + `code_compare.py`.  
6. `streamlit_app.py` or `main.py`, whichever UI you use.
