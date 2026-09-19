import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from prompt_engine import PromptEngine

load_dotenv()

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class AgentError(Exception):
    """Raised when BugSense cannot complete an analysis request."""


class BugSenseAgent:
    def __init__(self, model_id: str | None = None, retries: int = 3):
        self.engine = PromptEngine()
        self.model_id = model_id or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        self.retries = retries
        self._client = None

    @staticmethod
    def api_key_configured() -> bool:
        load_dotenv()
        return bool(os.getenv("GEMINI_API_KEY", "").strip())

    def _client_or_raise(self):
        if not self.api_key_configured():
            raise AgentError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        if self._client is None:
            self._client = genai.Client()
        return self._client

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if status in RETRYABLE_STATUS_CODES:
            return True
        message = str(exc).lower()
        retry_tokens = (
            "timeout",
            "timed out",
            "unavailable",
            "temporarily",
            "connection",
            "reset",
            "rate limit",
            "resource exhausted",
            "503",
            "429",
        )
        return any(token in message for token in retry_tokens)

    def analyze(self, parsed: dict) -> str:
        return self.run(self.engine.build(parsed))

    def run(self, prompt_list: list) -> str:
        if not prompt_list or "content" not in prompt_list[0]:
            raise AgentError("Prompt is empty; nothing to analyze.")

        user_text = prompt_list[0]["content"]
        config = types.GenerateContentConfig(
            system_instruction=self.engine.system_prompt(),
            temperature=0.2,
        )
        client = self._client_or_raise()
        last_error = None
        attempts_used = 0

        for attempt in range(self.retries):
            attempts_used = attempt + 1
            try:
                response = client.models.generate_content(
                    model=self.model_id,
                    contents=user_text,
                    config=config,
                )
                text = getattr(response, "text", None)
                if not text:
                    raise AgentError("Gemini returned an empty response.")
                return text
            except AgentError:
                raise
            except Exception as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt == self.retries - 1:
                    break
                wait = 2 ** attempt
                print(f"[retry {attempt + 1}] transient API error: {exc}; waiting {wait}s")
                time.sleep(wait)

        raise AgentError(
            f"Could not complete Gemini request "
            f"(attempt {attempts_used}/{self.retries}): {last_error}"
        )
