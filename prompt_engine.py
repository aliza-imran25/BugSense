SYSTEM_PROMPT = """You are a senior software engineer and patient educator.
A student has submitted code for analysis. Your job is NOT just to fix it —
it is to help them understand WHAT is wrong, if anything, and WHY.

If the code is valid and has no obvious bug, say so clearly. Do not invent a bug.

You MUST respond in exactly three labeled sections:
[Bug Type]       — the category of bug (e.g. off-by-one, null dereference), or "None" if no bug is found
[Root Cause]     — a clear, step-by-step explanation of WHY this fails, or why it is correct
[Corrected Code] — the fixed code with inline comments on every change; if no fix is needed, repeat the original code

Do not skip sections. Do not add anything outside these sections."""


class PromptEngine:
    def build(self, parsed: dict) -> list[dict]:
        lang = parsed.get("language") or "unknown"
        code = parsed.get("code") or ""
        error = parsed.get("error") or ""
        filename = parsed.get("filename") or ""

        header = f"Language: {lang}"
        if filename:
            header += f"\nFilename: {filename}"
        if lang == "unknown":
            header += "\n(Language could not be detected; infer it from the code.)"

        user_msg = f"{header}\n\nCode:\n```{lang}\n{code}\n```\n\n"
        if error:
            user_msg += f"Error message:\n{error}\n\n"

        user_msg += (
            "Now reason step by step:\n"
            "1. What TYPE of bug is this? If there is none, say None.\n"
            "2. WHY does the code fail, or why is it correct? Trace through it.\n"
            "3. Show the corrected code with comments, or the original if unchanged.\n"
        )
        return [{"role": "user", "content": user_msg}]

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT
