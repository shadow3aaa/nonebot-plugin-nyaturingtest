import time

from langchain.embeddings.base import Embeddings
from nonebot import logger
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
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "input": inputs}

        retries = 0
        last_exception = None

        while retries <= self.max_retries:
            try:
                response = requests.post(self.endpoint, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                data = response.json().get("data", [])
                return [item.get("embedding", []) for item in data]
            except requests.exceptions.Timeout as e:
                last_exception = e
                retries += 1
                if retries <= self.max_retries:
                    logger.warning(f"请求嵌入模型超时 ({self.timeout}秒)，正在进行第 {retries} 次重试...")
                    time.sleep(self.retry_delay)
            except requests.exceptions.RequestException as e:
                last_exception = e
                if retries <= self.max_retries:
                    logger.warning(f"请求嵌入模型失败: {e}")
                break

        # 如果所有重试都失败，记录错误并返回空向量
        logger.error(f"嵌入请求失败: {last_exception}")

        # 返回与输入长度匹配的空向量列表，确保类型一致
        if last_exception:
            # 创建空向量作为回退方案
            empty_vectors = []
            for _ in inputs:
                # 使用大小为1的零向量作为回退
                empty_vectors.append([0.0])
            logger.warning(f"由于请求失败，返回{len(empty_vectors)}个空向量作为回退")
            return empty_vectors

        # 这行代码理论上不会被执行，但添加它确保函数总是返回
        return [[0.0] for _ in inputs]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]
