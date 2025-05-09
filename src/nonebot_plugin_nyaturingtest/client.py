from google import genai
from openai import OpenAI

from .config import plugin_config


class LLMClient:
    def __init__(self, client: OpenAI | genai.Client):
        if isinstance(client, genai.Client):
            self.type = "google"
        elif isinstance(client, OpenAI):
            self.type = "openai"
        self.client = client

    def generate_response(self, prompt: str) -> str | None:
        if isinstance(self.client, genai.Client):
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text

        elif isinstance(self.client, OpenAI):
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=plugin_config.nyaturingtest_chat_openai_model,
                temperature=0.5,
                timeout=30,
            )
            return response.choices[0].message.content
        else:
            raise ValueError("Unsupported client type")
