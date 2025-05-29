import re

from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def generate_response(self, prompt: str, model: str) -> str | None:
        response = await self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            temperature=0.5,
            timeout=30,
        )
        content = response.choices[0].message.content
        if content:
            return remove_leading_think(content)
        else:
            return None


def remove_leading_think(text: str) -> str:
    # 匹配开头连续的 <think>...</think> 或 <think/> 块
    pattern = r"^(?:\s*<think>(.*?)</think>\s*|\s*<think\s*/?>\s*)+"
    return re.sub(pattern, "", text, flags=re.DOTALL).lstrip()
