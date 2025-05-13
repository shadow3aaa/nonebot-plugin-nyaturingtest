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
        try:
            self.hippo = HippoRAG(
                llm_model_name=llm_model,
                llm_base_url=llm_base_url,
                llm_api_key=llm_api_key,
                embedding_model_name=embedding_model,
                embedding_api_key=embedding_api_key,
                embedding_base_url="https://api.siliconflow.cn/v1",
                save_dir=persist_directory,
            )
            logger.info(f"已创建/加载新的HippoRAG集合: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create HippoRAG collection: {e}")

        # 用于跟踪上次清理的时间
        self._last_forget = datetime.now()

    def _now_str(self) -> str:
        """返回当前时间的 ISO 格式字符串"""
        return datetime.now().isoformat()

    def clear(self) -> None:
        """
        清除所有记忆
        """
        # 删除索引文件
        if os.path.exists(self.persist_directory):
            for file in os.listdir(self.persist_directory):
                file_path = os.path.join(self.persist_directory, file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        os.rmdir(file_path)
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {e}")
        else:
            logger.warning(f"Persist directory {self.persist_directory} does not exist.")
        # 重新创建索引
        try:
            self.hippo = HippoRAG(
                llm_model_name=self.hippo.global_config.llm_name,
                llm_base_url=self.hippo.global_config.llm_base_url,
                llm_api_key=self.hippo.global_config.llm_api_key,
                embedding_model_name=self.hippo.global_config.embedding_model_name,
                embedding_api_key=self.hippo.global_config.embedding_api_key,
                embedding_base_url=self.hippo.global_config.embedding_base_url,
                save_dir=self.persist_directory,
            )
        except Exception as e:
            logger.error(f"Failed to recreate HippoRAG collection: {e}")
            return
        logger.info("已清除所有记忆")

    def add_texts(self, texts: list[str]) -> None:
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
