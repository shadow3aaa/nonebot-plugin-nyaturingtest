from langchain.embeddings.base import Embeddings
import requests


class SiliconFlowEmbeddings(Embeddings):
    """
    使用 SiliconFlow API 的自定义嵌入模型适配器。
    文档：https://docs.siliconflow.cn/cn/api-reference/embeddings/create-embeddings
    """

    def __init__(
        self,
        api_key: str,
        model: str = "BAAI/bge-large-zh-v1.5",
        endpoint: str = "https://api.siliconflow.cn/v1/embeddings",
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "input": inputs}
        response = requests.post(self.endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json().get("data", [])
        return [item.get("embedding", []) for item in data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]
