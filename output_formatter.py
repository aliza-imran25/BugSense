import re

class OutputFormatter:
    SECTIONS = ("Bug Type", "Root Cause", "Corrected Code")
    COLORS = {
        "Bug Type": "\033[91m",
        "Root Cause": "\033[93m",
        "Corrected Code": "\033[92m",
    }
    RESET = "\033[0m"
    _SECTION_RE = re.compile(
        r"\[(Bug Type|Root Cause|Corrected Code)\]\s*(.*?)(?=\[(?:Bug Type|Root Cause|Corrected Code)\]|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    def parse_sections(self, raw: str) -> dict:
        result = {name: "" for name in self.SECTIONS}
        for match in self._SECTION_RE.finditer(raw or ""):
            key = match.group(1).strip()
            canonical = next((name for name in self.SECTIONS if name.lower() == key.lower()), key)
            result[canonical] = match.group(2).strip()
        return result

    def to_markdown(self, raw: str) -> str:
        sections = self.parse_sections(raw)
        if not any(sections.values()):
            return raw
        parts = []
        for name in self.SECTIONS:
            content = sections.get(name) or "*(not found)*"
            parts.append(f"### {name}\n\n{content}")
        return "\n\n".join(parts)

    def display(self, raw: str) -> None:
        sections = self.parse_sections(raw)
        print("\n" + "─" * 52)
        for name in self.SECTIONS:
            color = self.COLORS.get(name, "")
            content = sections.get(name) or "(not found)"
            print(f"\n{color}▶ {name}{self.RESET}")
            print(content)
        print("\n" + "─" * 52 + "\n")
