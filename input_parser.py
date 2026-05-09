# input_parser.py
import re

class InputParser:
    LANG_HINTS = {
        "python": [r"def ", r"import ", r"print\("],
        "java":   [r"public class", r"System\.out"],
        "c":      [r"#include", r"printf\(", r"int main"],
    }
    MAX_LINES = 100  # scope limit for Module 1

    def detect_language(self, code: str) -> str:
        for lang, patterns in self.LANG_HINTS.items():
            if any(re.search(p, code) for p in patterns):
                return lang
        return "unknown"

    def parse(self, code: str, error: str = "") -> dict:
        lines = code.strip().splitlines()
        if len(lines) > self.MAX_LINES:
            print(f"[warn] Truncated to {self.MAX_LINES} lines.")
            lines = lines[:self.MAX_LINES]
        clean_code = "\n".join(lines)
        return {
            "code":     clean_code,
            "error":    error,
            "language": self.detect_language(clean_code),
            "lines":    len(lines),
        }