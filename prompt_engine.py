SYSTEM_PROMPT = """You are a senior software engineer and patient educator.
A student has submitted broken code. Your job is NOT just to fix it —
it is to help them understand WHY it is broken.

You MUST respond in exactly three labeled sections:
[Bug Type]       — the category of bug (e.g. off-by-one, null dereference)
[Root Cause]     — a clear, step-by-step explanation of WHY this fails
[Corrected Code] — the fixed code with inline comments on every change

Do not skip sections. Do not add anything outside these sections."""

class PromptEngine:
    def build(self, parsed: dict) -> list[dict]:
        lang    = parsed["language"]
        code    = parsed["code"]
        error   = parsed["error"]

        user_msg = (
            f"Language: {lang}\n\n"
            f"Code:\n```{lang}\n{code}\n```\n\n"
        )
        if error:
            user_msg += f"Error message:\n{error}\n\n"

        user_msg += (
            "Now reason step by step:\n"
            "1. What TYPE of bug is this?\n"
            "2. WHY does the code fail? Trace through it.\n"
            "3. Show the corrected code with comments.\n"
        )
        return [
            {"role": "user", "content": user_msg}
        ]

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT