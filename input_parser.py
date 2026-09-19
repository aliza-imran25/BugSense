from pathlib import Path

class InputParser:
    """Normalize source input before it is sent to the model."""

    LANG_HINTS = {
        "python": (r"def ", r"import ", r"print("),
        "java": (r"public class", r"System.out"),
        "c": (r"#include", r"printf(", r"int main"),
    }
    EXTENSIONS = {
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
    MAX_LINES = 100
    MAX_BYTES = 200_000

    def detect_language(self, code: str, filename: str = "") -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in self.EXTENSIONS:
            return self.EXTENSIONS[suffix]

        for lang, patterns in self.LANG_HINTS.items():
            if any(token in code for token in patterns):
                return lang
        return "unknown"

    def parse(self, code: str, error: str = "", filename: str = "") -> dict:
        warnings: list[str] = []
        raw = code or ""

        if len(raw.encode("utf-8")) > self.MAX_BYTES:
            warnings.append(
                f"Input exceeds {self.MAX_BYTES} bytes; truncated before analysis."
            )
            raw = raw.encode("utf-8")[: self.MAX_BYTES].decode("utf-8", errors="ignore")

        lines = raw.strip().splitlines()
        if len(lines) > self.MAX_LINES:
            warnings.append(
                f"Truncated to {self.MAX_LINES} lines (parser limit)."
            )
            lines = lines[: self.MAX_LINES]

        clean_code = "\n".join(lines)
        language = self.detect_language(clean_code, filename)
        return {
            "code": clean_code,
            "error": (error or "").strip(),
            "language": language,
            "filename": filename,
            "lines": len(lines),
            "warnings": warnings,
        }
