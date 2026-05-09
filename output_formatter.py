import re

class OutputFormatter:
    SECTIONS = ["Bug Type", "Root Cause", "Corrected Code"]
    COLORS = {
        "Bug Type":       "\033[91m",  # red
        "Root Cause":     "\033[93m",  # yellow
        "Corrected Code": "\033[92m",  # green
    }
    RESET = "\033[0m"

    def parse_sections(self, raw: str) -> dict:
        result = {}
        pattern = r"\[(.+?)\](.*?)(?=\[|\Z)"
        for match in re.finditer(pattern, raw, re.DOTALL):
            key = match.group(1).strip()
            val = match.group(2).strip()
            result[key] = val
        return result

    def display(self, raw: str):
        sections = self.parse_sections(raw)
        print("\n" + "─"*52)
        for name in self.SECTIONS:
            color = self.COLORS.get(name, "")
            content = sections.get(name, "(not found)")
            print(f"\n{color}▶ {name}{self.RESET}")
            print(f"{content}")
        print("\n" + "─"*52 + "\n")