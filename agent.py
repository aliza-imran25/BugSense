import os
from google import genai
from google.genai import types
from prompt_engine import PromptEngine
from dotenv import load_dotenv

load_dotenv()

class BugSenseAgent:
    def __init__(self):
        # The client automatically picks up GEMINI_API_KEY from your .env
        self.client = genai.Client()
        self.engine = PromptEngine()
        self.model_id = "gemini-3-flash-preview" # Latest 2026 flash model
        self.retries = 3

    def run(self, prompt_list: list) -> str:
        # Extract user text from your PromptEngine structure
        user_text = prompt_list[0]["content"]
        
        # Configure the system instruction
        config = types.GenerateContentConfig(
            system_instruction=self.engine.system_prompt(),
            temperature=0.2  # Lower temperature for more stable code analysis
        )

        for attempt in range(self.retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=user_text,
                    config=config
                )
                return response.text
            except Exception as e:
                print(f"[retry {attempt+1}] API error: {e}")
        
        return "Error: could not reach the Gemini API after 3 attempts."