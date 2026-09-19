"""Extract corrected sources and render a side-by-side red/green diff."""

from __future__ import annotations

import html
import re
from difflib import SequenceMatcher

_FENCE_RE = re.compile(r"```(?:[\w.+-]*)\n(.*?)```", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,3})\s+(\S.+)$", re.MULTILINE)


def strip_fence(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    fences = _FENCE_RE.findall(raw)
    if fences:
        return fences[0].strip("\n")
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip("\n")
    return raw


def extract_corrected_files(section: str) -> list[tuple[str, str]]:
    """Parse [Corrected Code] into (filename, source) pairs."""
    text = (section or "").strip()
    if not text:
        return []

    headings = list(_HEADING_RE.finditer(text))
    if headings:
        files: list[tuple[str, str]] = []
        for index, match in enumerate(headings):
            name = match.group(2).strip().strip("`")
            start = match.end()
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            body = strip_fence(text[start:end].strip())
            if body:
                files.append((name, body))
        if files:
            return files

    body = strip_fence(text)
    return [("", body)] if body else []


def reconstruct_patch_sides(patch: str) -> tuple[str, str]:
    """Rebuild old/new snippets from a unified diff hunk (context-only, not a full file)."""
    old_lines: list[str] = []
    new_lines: list[str] = []
    for line in (patch or "").splitlines():
        if line.startswith(
            ("diff ", "index ", "---", "+++", "@@", "new file", "deleted file")
        ):
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("-"):
            old_lines.append(line[1:])
        elif line.startswith("+"):
            new_lines.append(line[1:])
        elif line.startswith(" "):
            old_lines.append(line[1:])
            new_lines.append(line[1:])
    return "\n".join(old_lines), "\n".join(new_lines)


def _looks_like_diff(text: str) -> bool:
    return bool(re.search(r"^(\+\+\+|---|@@ |diff --git )", text or "", re.MULTILINE))


def pair_sources(parsed: dict, corrected_section: str) -> list[tuple[str, str, str]]:
    """Return (label, original, corrected) triples for the comparison UI."""
    extracted = extract_corrected_files(corrected_section)
    if not extracted:
        return []

    by_name = {name.replace("\\", "/"): code for name, code in extracted if name}
    by_base = {name.rsplit("/", 1)[-1]: code for name, code in by_name.items()}

    mode = parsed.get("mode") or "snippet"
    pairs: list[tuple[str, str, str]] = []

    if mode == "files":
        for item in parsed.get("files") or []:
            filename = item.get("filename") or "file"
            key = filename.replace("\\", "/")
            corrected = by_name.get(key) or by_base.get(key.rsplit("/", 1)[-1])
            if corrected is None and len(extracted) == 1 and len(parsed.get("files") or []) == 1:
                corrected = extracted[0][1]
            if corrected is None:
                continue
            pairs.append((filename, item.get("code") or "", corrected))
        if not pairs and len(extracted) == 1:
            combined = parsed.get("code") or ""
            pairs.append((extracted[0][0] or "project", combined, extracted[0][1]))
        return pairs

    if mode == "diff":
        patches = parsed.get("patches") or []
        for item in patches:
            filename = item.get("filename") or "file"
            old, new_from_patch = reconstruct_patch_sides(item.get("patch") or "")
            key = filename.replace("\\", "/")
            corrected = by_name.get(key) or by_base.get(key.rsplit("/", 1)[-1])
            if corrected is None and len(extracted) == 1 and len(patches) == 1:
                corrected = extracted[0][1]
            if corrected is None:
                continue
            if _looks_like_diff(corrected):
                _, corrected = reconstruct_patch_sides(corrected)
            original = old or new_from_patch
            pairs.append((filename, original, corrected))
        if not pairs and extracted:
            original = parsed.get("code") or ""
            if _looks_like_diff(original):
                original, _ = reconstruct_patch_sides(original)
            pairs.append((extracted[0][0] or "diff", original, extracted[0][1]))
        return pairs

    original = parsed.get("code") or ""
    label = parsed.get("filename") or extracted[0][0] or "snippet"
    return [(label, original, extracted[0][1])]


def diff_rows(original: str, corrected: str) -> list[tuple[str, str | None, str | None, int | None, int | None]]:
    left = (original or "").splitlines()
    right = (corrected or "").splitlines()
    rows: list[tuple[str, str | None, str | None, int | None, int | None]] = []
    matcher = SequenceMatcher(a=left, b=right, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                rows.append(("eq", left[i1 + offset], right[j1 + offset], i1 + offset + 1, j1 + offset + 1))
        elif tag == "delete":
            for index in range(i1, i2):
                rows.append(("del", left[index], None, index + 1, None))
        elif tag == "insert":
            for index in range(j1, j2):
                rows.append(("add", None, right[index], None, index + 1))
        else:
            left_slice = left[i1:i2]
            right_slice = right[j1:j2]
            n = max(len(left_slice), len(right_slice))
            for offset in range(n):
                old = left_slice[offset] if offset < len(left_slice) else None
                new = right_slice[offset] if offset < len(right_slice) else None
                old_no = i1 + offset + 1 if old is not None else None
                new_no = j1 + offset + 1 if new is not None else None
                if old is None:
                    rows.append(("add", None, new, None, new_no))
                elif new is None:
                    rows.append(("del", old, None, old_no, None))
                else:
                    rows.append(("chg", old, new, old_no, new_no))
    return rows


def _cell(kind: str, line: str | None, number: int | None, side: str) -> str:
    css = "eq"
    if kind == "del" or (kind == "chg" and side == "left"):
        css = "del"
    elif kind == "add" or (kind == "chg" and side == "right"):
        css = "add"
    if line is None:
        return '<td class="empty"></td><td class="empty"></td>'
    num = "" if number is None else str(number)
    return (
        f'<td class="num {css}">{html.escape(num)}</td>'
        f'<td class="code {css}">{html.escape(line)}</td>'
    )


def unified_color_lines(original: str, corrected: str) -> str:
    """Terminal unified diff with red deletions and green additions."""
    red = "\033[91m"
    green = "\033[92m"
    reset = "\033[0m"
    rows = diff_rows(original, corrected)
    lines = []
    for kind, old, new, _, _ in rows:
        if kind == "eq" and old is not None:
            lines.append(f"  {old}")
        elif kind == "del" and old is not None:
            lines.append(f"{red}- {old}{reset}")
        elif kind == "add" and new is not None:
            lines.append(f"{green}+ {new}{reset}")
        elif kind == "chg":
            if old is not None:
                lines.append(f"{red}- {old}{reset}")
            if new is not None:
                lines.append(f"{green}+ {new}{reset}")
    return "\n".join(lines)


def side_by_side_html(original: str, corrected: str) -> str:
    rows = diff_rows(original, corrected)
    if not rows:
        rows = [("eq", "", "", 1, 1)]
    body = []
    for kind, old, new, old_no, new_no in rows:
        body.append(
            "<tr>"
            + _cell(kind, old, old_no, "left")
            + _cell(kind, new, new_no, "right")
            + "</tr>"
        )
    table = "\n".join(body)
    return f"""
<style>
.bs-diff {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  overflow: auto;
  max-height: 520px;
  color: #1f2328;
  background: #fff;
}}
.bs-diff table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
.bs-diff th {{
  position: sticky; top: 0; background: #f6f8fa; text-align: left;
  padding: 8px 10px; border-bottom: 1px solid #d0d7de; font-weight: 600;
}}
.bs-diff td {{ vertical-align: top; white-space: pre; padding: 1px 8px; }}
.bs-diff .num {{
  width: 3.2em; color: #656d76; text-align: right; user-select: none;
  border-right: 1px solid #d0d7de;
}}
.bs-diff .code {{ overflow-wrap: anywhere; white-space: pre-wrap; }}
.bs-diff .del {{ background: #ffd7d5; }}
.bs-diff .add {{ background: #ccffd8; }}
.bs-diff .empty {{ background: #f6f8fa; }}
.bs-legend {{ font-size: 0.9rem; margin: 0 0 0.6rem 0; color: #444; }}
.bs-swatch {{
  display: inline-block; padding: 1px 8px; border-radius: 4px; margin-right: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}
</style>
<p class="bs-legend">
  <span class="bs-swatch del" style="background:#ffd7d5;">− removed</span>
  <span class="bs-swatch add" style="background:#ccffd8;">+ added</span>
  Unchanged lines stay white. Left is your code, right is the fix.
</p>
<div class="bs-diff">
<table>
  <thead>
    <tr>
      <th colspan="2">Your code</th>
      <th colspan="2">Corrected code</th>
    </tr>
  </thead>
  <tbody>
    {table}
  </tbody>
</table>
</div>
"""
