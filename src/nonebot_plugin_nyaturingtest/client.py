from openai import OpenAI


class LLMClient:
    def __init__(self, client: OpenAI):
        self.client = client

    def generate_response(self, prompt: str, model: str) -> str | None:
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.5,
            timeout=30,
        )
        return response.choices[0].message.content
