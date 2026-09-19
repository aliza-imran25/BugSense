import re
from pathlib import Path

SOURCE_EXTENSIONS = {
    ".py": "python",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".sql": "sql",
    ".kt": "kotlin",
    ".swift": "swift",
}

_SECRET_RE = re.compile(
    r"(?i)((?:api[_-]?key|secret|token|password|passwd|authorization)\s*[=:]\s*)(['\"]?)([^\s'\"]{8,})(\2)"
)
_CHUNK_START = re.compile(
    r"^(def |async def |class |function |export (?:default )?function |export class |"
    r"pub (?:async )?fn |fn |func )"
)


class InputParser:
    """Normalize source input before it is sent to the model."""

    LANG_HINTS = {
        "python": ("def ", "import ", "print("),
        "java": ("public class", "System.out"),
        "c": ("#include", "printf(", "int main"),
        "javascript": ("function ", "const ", "console.log"),
        "typescript": ("interface ", "type ", ": string"),
        "go": ("package ", "func ", "fmt."),
        "sql": ("SELECT ", "CREATE TABLE", "INSERT INTO"),
        "rust": ("fn ", "let mut ", "impl "),
    }
    EXTENSIONS = SOURCE_EXTENSIONS
    MAX_LINES = 400
    MAX_BYTES = 500_000
    MAX_FILES = 20
    MAX_TOTAL_LINES = 1600
    MAX_DIFF_LINES = 1500

    def detect_language(self, code: str, filename: str = "") -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in self.EXTENSIONS:
            return self.EXTENSIONS[suffix]

        for lang, patterns in self.LANG_HINTS.items():
            if any(token in code for token in patterns):
                return lang
        return "unknown"

    def _truncate_text(self, raw: str, max_lines: int, warnings: list[str], label: str) -> str:
        text = redact_secrets(raw or "", warnings)
        if len(text.encode("utf-8")) > self.MAX_BYTES:
            warnings.append(f"{label} exceeds {self.MAX_BYTES} bytes; truncated.")
            text = text.encode("utf-8")[: self.MAX_BYTES].decode("utf-8", errors="ignore")

        lines = text.strip().splitlines()
        if len(lines) > max_lines:
            warnings.append(f"{label}: Truncated to {max_lines} lines.")
            lines = lines[:max_lines]
        return "\n".join(lines)

    def parse(self, code: str, error: str = "", filename: str = "") -> dict:
        warnings: list[str] = []
        redacted = redact_secrets(code or "", warnings)
        chunks = chunk_by_top_level(redacted, self.MAX_LINES)
        if len(chunks) > 1:
            warnings.append(
                f"{filename or 'Input'} was split into {len(chunks)} function/class chunks."
            )
            stem = filename or "snippet"
            items = [(f"{stem}#part{i + 1}", chunk) for i, chunk in enumerate(chunks)]
            parsed = self.parse_files(items, error)
            parsed["warnings"] = warnings + parsed.get("warnings", [])
            return parsed
        clean_code = self._truncate_text(redacted, self.MAX_LINES, warnings, filename or "Input")
        language = self.detect_language(clean_code, filename)
        return {
            "mode": "snippet",
            "code": clean_code,
            "error": (error or "").strip(),
            "language": language,
            "filename": filename,
            "lines": len(clean_code.splitlines()) if clean_code else 0,
            "files": [
                {
                    "filename": filename or "snippet",
                    "language": language,
                    "code": clean_code,
                    "lines": len(clean_code.splitlines()) if clean_code else 0,
                }
            ]
            if clean_code.strip()
            else [],
            "patches": [],
            "diff_source": "",
            "warnings": warnings,
        }

    def parse_files(self, items: list[tuple[str, str]], error: str = "") -> dict:
        """Parse several files as one project so cross-file bugs can be found."""
        warnings: list[str] = []
        files: list[dict] = []
        total_lines = 0

        if len(items) > self.MAX_FILES:
            warnings.append(
                f"Only the first {self.MAX_FILES} of {len(items)} files were included."
            )
            items = items[: self.MAX_FILES]

        for filename, code in items:
            remaining = self.MAX_TOTAL_LINES - total_lines
            if remaining <= 0:
                warnings.append("Stopped adding files after the total line budget.")
                break
            label = filename or "file"
            truncated = self._truncate_text(
                code, min(self.MAX_LINES, remaining), warnings, label
            )
            if not truncated.strip():
                warnings.append(f"{label} is empty; skipped.")
                continue
            language = self.detect_language(truncated, filename)
            line_count = len(truncated.splitlines())
            total_lines += line_count
            files.append(
                {
                    "filename": filename or "file",
                    "language": language,
                    "code": truncated,
                    "lines": line_count,
                }
            )

        languages = {item["language"] for item in files}
        primary = files[0]["language"] if files else "unknown"
        if len(languages) > 1:
            primary = "mixed"

        combined = "\n\n".join(
            f"# {item['filename']}\n{item['code']}" for item in files
        )
        return {
            "mode": "files",
            "code": combined,
            "error": (error or "").strip(),
            "language": primary,
            "filename": files[0]["filename"] if files else "",
            "lines": total_lines,
            "files": files,
            "patches": [],
            "diff_source": "",
            "warnings": warnings,
        }

    def parse_diff(self, patch_text: str, error: str = "", source: str = "") -> dict:
        warnings: list[str] = []
        raw = self._truncate_text(
            patch_text, self.MAX_DIFF_LINES, warnings, source or "Diff"
        )
        patches = split_unified_diff(raw)
        if not patches:
            warnings.append("No file hunks found in the diff.")

        kept: list[dict] = []
        for patch in patches[: self.MAX_FILES]:
            language = self.detect_language(patch["patch"], patch["filename"])
            kept.append(
                {
                    "filename": patch["filename"],
                    "language": language,
                    "patch": patch["patch"],
                    "lines": patch["patch"].count("\n") + 1,
                }
            )
        if len(patches) > self.MAX_FILES:
            warnings.append(
                f"Only the first {self.MAX_FILES} changed files from the diff were included."
            )

        languages = {item["language"] for item in kept}
        primary = kept[0]["language"] if kept else "unknown"
        if len(languages) > 1:
            primary = "mixed"

        return {
            "mode": "diff",
            "code": raw,
            "error": (error or "").strip(),
            "language": primary,
            "filename": kept[0]["filename"] if kept else "",
            "lines": len(raw.splitlines()) if raw else 0,
            "files": [],
            "patches": kept,
            "diff_source": source,
            "warnings": warnings,
        }


def split_unified_diff(patch_text: str) -> list[dict]:
    """Split a unified diff into per-file patches; skip binary blobs."""
    text = patch_text or ""
    if not text.strip():
        return []

    chunks: list[str]
    if "diff --git " in text:
        parts = text.split("\ndiff --git ")
        chunks = []
        for index, part in enumerate(parts):
            part = part.strip("\n")
            if not part.strip():
                continue
            if index == 0 and part.startswith("diff --git "):
                chunks.append(part)
            elif index == 0:
                chunks.append(part)
            else:
                chunks.append("diff --git " + part)
    else:
        chunks = [text]

    result: list[dict] = []
    for chunk in chunks:
        if "Binary files " in chunk or "GIT binary patch" in chunk:
            continue
        filename = _filename_from_diff_chunk(chunk)
        if not filename:
            continue
        suffix = Path(filename).suffix.lower()
        if suffix and suffix not in SOURCE_EXTENSIONS:
            continue
        result.append({"filename": filename, "patch": chunk.strip() + "\n"})
    return result


def _filename_from_diff_chunk(chunk: str) -> str:
    for line in chunk.splitlines():
        if line.startswith("+++ b/"):
            return line[6:].strip()
        if line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            path = line[4:].strip()
            if path.startswith("b/"):
                return path[2:]
            return path
    for line in chunk.splitlines():
        if line.startswith("--- a/"):
            return line[6:].strip()
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                return parts[3].removeprefix("b/")
    return ""


def redact_secrets(text: str, warnings: list[str] | None = None) -> str:
    """Mask common key/token assignments before the code is sent to the model."""

    def _replace(match: re.Match) -> str:
        return f"{match.group(1)}{match.group(2)}***REDACTED***{match.group(4)}"

    redacted, count = _SECRET_RE.subn(_replace, text or "")
    if count and warnings is not None:
        warnings.append(f"Redacted {count} possible secret value(s) before sending to the API.")
    return redacted


def chunk_by_top_level(code: str, max_lines: int) -> list[str]:
    """Split oversized files on top-level defs/classes so they can be analyzed in parts."""
    lines = (code or "").splitlines()
    if len(lines) <= max_lines:
        return ["\n".join(lines)] if lines else [code or ""]

    starts = [index for index, line in enumerate(lines) if _CHUNK_START.match(line)]
    if len(starts) < 2:
        return ["\n".join(lines)]

    if starts[0] != 0:
        starts = [0] + starts

    raw_chunks: list[list[str]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        raw_chunks.append(lines[start:end])

    packed: list[str] = []
    current: list[str] = []
    for piece in raw_chunks:
        if current and len(current) + len(piece) > max_lines:
            packed.append("\n".join(current))
            current = list(piece)
            if len(current) > max_lines:
                packed.append("\n".join(current[:max_lines]))
                current = []
        else:
            current.extend(piece)
    if current:
        packed.append("\n".join(current[:max_lines]))
    return packed or ["\n".join(lines[:max_lines])]
