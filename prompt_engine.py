SYSTEM_PROMPT = """You are a senior software engineer and patient educator.
A student has submitted code for analysis. Your job is NOT just to fix it —
it is to help them understand WHAT is wrong, if anything, and WHY.

If the code is valid and has no obvious bug, say so clearly. Do not invent a bug.

You MUST respond in exactly three labeled sections:
[Bug Type]       — the category of bug (e.g. off-by-one, null dereference, cross-file contract mismatch), or "None" if no bug is found
[Root Cause]     — a clear, step-by-step explanation of WHY this fails, or why it is correct. Name files when the bug spans modules.
[Corrected Code] — the FULL updated source (every line, not a partial snippet) inside a markdown fence so it can be compared line-by-line. Put short comments only on changed lines. If no fix is needed, repeat the original. For multiple files or a diff, use a ### path heading then a fence for each file you change.

Do not skip sections. Do not add anything outside these sections."""


class PromptEngine:
    def build(self, parsed: dict) -> list[dict]:
        mode = parsed.get("mode") or "snippet"
        if mode == "files":
            user_msg = self._build_files(parsed)
        elif mode == "diff":
            user_msg = self._build_diff(parsed)
        else:
            user_msg = self._build_snippet(parsed)
        return [{"role": "user", "content": user_msg}]

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def _error_block(self, parsed: dict) -> str:
        error = parsed.get("error") or ""
        return f"Error message:\n{error}\n\n" if error else ""

    def _closing(self, extra: str) -> str:
        return (
            "Now reason step by step:\n"
            "1. What TYPE of bug is this? If there is none, say None.\n"
            "2. WHY does the code fail, or why is it correct? Trace through it.\n"
            f"3. {extra}\n"
        )

    def _build_snippet(self, parsed: dict) -> str:
        lang = parsed.get("language") or "unknown"
        code = parsed.get("code") or ""
        filename = parsed.get("filename") or ""

        header = f"Language: {lang}"
        if filename:
            header += f"\nFilename: {filename}"
        if lang == "unknown":
            header += "\n(Language could not be detected; infer it from the code.)"

        user_msg = f"{header}\n\nCode:\n```{lang}\n{code}\n```\n\n"
        user_msg += self._error_block(parsed)
        user_msg += self._closing(
            "Show the FULL corrected file in a markdown fence (all lines, not a snippet), or the original if unchanged."
        )
        return user_msg

    def _build_files(self, parsed: dict) -> str:
        files = parsed.get("files") or []
        names = ", ".join(item["filename"] for item in files)
        user_msg = (
            "Mode: multi-file project\n"
            f"Files: {names}\n"
            "Bugs may live in one file or in how these files call each other "
            "(wrong import, mismatched types, caller vs callee).\n\n"
        )
        for item in files:
            lang = item.get("language") or "unknown"
            name = item.get("filename") or "file"
            user_msg += f"File: {name} ({lang})\n```{lang}\n{item.get('code', '')}\n```\n\n"
        user_msg += self._error_block(parsed)
        user_msg += self._closing(
            "Show FULL corrected files in markdown fences. Use a ### filename heading for each file you change."
        )
        return user_msg

    def _build_diff(self, parsed: dict) -> str:
        source = parsed.get("diff_source") or "pasted diff"
        patches = parsed.get("patches") or []
        user_msg = (
            "Mode: git / unified diff\n"
            f"Source: {source}\n"
            "Focus on the changed hunks. Mention nearby context if the real bug is a caller/callee mismatch.\n\n"
        )
        if patches:
            for item in patches:
                name = item.get("filename") or "file"
                lang = item.get("language") or "unknown"
                user_msg += f"Changed file: {name} ({lang})\n```diff\n{item.get('patch', '')}\n```\n\n"
        else:
            user_msg += f"```diff\n{parsed.get('code', '')}\n```\n\n"
        user_msg += self._error_block(parsed)
        user_msg += self._closing(
            "Show FULL updated files (or a corrected patch) in markdown fences. Use ### filename headings."
        )
        return user_msg
