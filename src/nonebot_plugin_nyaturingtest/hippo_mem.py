from datetime import datetime
import os

from nonebot import logger

from hipporag import HippoRAG


class HippoMemory:
    def __init__(
        self,
        llm_model: str,
        llm_base_url: str,
        llm_api_key: str,
        embedding_api_key: str,
        persist_directory: str = "./hippo_index",
        collection_name: str = "hippo_collection",
        embedding_model: str = "BAAI/bge-large-zh-v1.5",
    ):
        # 确保存储目录存在
        os.makedirs(persist_directory, exist_ok=True)

        # 初始化HippoRAG
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # 使用HippoRAG初始化记忆库
        # TODO: 从持久化目录加载现有集合
        try:
            self.hippo = HippoRAG(
                llm_model_name=llm_model,
                llm_base_url=llm_base_url,
                llm_api_key=llm_api_key,
                embedding_model_name=embedding_model,
                embedding_api_key=embedding_api_key,
                embedding_base_url="https://api.siliconflow.cn/v1/embeddings",
                save_dir=persist_directory,
            )
            logger.info(f"已创建新的HippoRAG集合: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create HippoRAG collection: {e}")

        # 用于跟踪上次清理的时间
        self._last_forget = datetime.now()

    def _now_str(self) -> str:
        """返回当前时间的 ISO 格式字符串"""
        return datetime.now().isoformat()

    def save(self):
        """持久化索引到本地文件夹。"""
        # TODO: 添加持久化逻辑
        pass

    def add_texts(
        self, texts: list[str]
    ) -> None:
        """
        添加文本到长期记忆，带语义去重功能

        Args:
            texts: 要添加的文本列表
        """
        self.hippo.index(texts)

    def retrieve(self, queries: list[str], k: int = 5) -> list[str]:
        """
        检索与查询相关的文本

        Args:
            query: 查询文本
            k: 返回的最大结果数

        Returns:
            包含检索结果的Document列表
        """
        results = self.hippo.retrieve(queries=queries, num_to_retrieve=k)
        # make ruff happy
        assert isinstance(results, list)
        return [doc for result in results for doc in result.docs]
