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
    ".ts": "typescript",
}


class InputParser:
    """Normalize source input before it is sent to the model."""

    LANG_HINTS = {
        "python": (r"def ", r"import ", r"print("),
        "java": (r"public class", r"System.out"),
        "c": (r"#include", r"printf(", r"int main"),
    }
    EXTENSIONS = SOURCE_EXTENSIONS
    MAX_LINES = 100
    MAX_BYTES = 200_000
    MAX_FILES = 12
    MAX_TOTAL_LINES = 400
    MAX_DIFF_LINES = 500

    def detect_language(self, code: str, filename: str = "") -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in self.EXTENSIONS:
            return self.EXTENSIONS[suffix]

        for lang, patterns in self.LANG_HINTS.items():
            if any(token in code for token in patterns):
                return lang
        return "unknown"

    def _truncate_text(self, raw: str, max_lines: int, warnings: list[str], label: str) -> str:
        text = raw or ""
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
        clean_code = self._truncate_text(code, self.MAX_LINES, warnings, filename or "Input")
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
