from datetime import datetime
import os
import shutil

from nonebot import logger
from transformers import AutoTokenizer, PreTrainedTokenizer, PreTrainedTokenizerFast

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
                embedding_model_name="BAAI/bge-m3",
                embedding_api_key=embedding_api_key,
                embedding_base_url="https://api.siliconflow.cn/v1",
                save_dir=persist_directory,
            )
            logger.info(f"已创建/加载新的HippoRAG集合: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create HippoRAG collection: {e}")

        # 用于跟踪上次清理的时间
        self._last_forget = datetime.now()
        # 缓存要索引的文本
        self._cache = ""
        # 初始化分词器
        self.tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3", trust_remote_code=True)

    def _now_str(self) -> str:
        """返回当前时间的 ISO 格式字符串"""
        return datetime.now().isoformat()

    def clear(self) -> None:
        """
        清除所有记忆
        """
        # 删除索引文件
        if os.path.exists(self.persist_directory):
            try:
                shutil.rmtree(self.persist_directory)
            except Exception as e:
                logger.error(f"Failed to delete persist directory: {e}")
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
        添加文本到缓存

        Args:
            texts: 要添加的文本列表
        """
        for text in texts:
            self._cache += text + "\n"

    def index(self):
        """
        对缓存的文本进行索引，整理到长期记忆
        """
        if self._cache:
            # 切割(BAAI/bge-m3上限为8192tokens)
            texts = _split_text_by_tokens(self._cache, self.tokenizer, max_tokens=8192, overlap=100)
            self.hippo.index(texts)
            logger.info(f"已索引 {len(texts)} 条缓存文本")
            self._cache = ""
        else:
            logger.info("没有缓存的文本需要索引")

    def retrieve(self, queries: list[str], k: int = 5) -> list[str]:
        """
        检索与查询相关的文本

        Args:
            query: 查询文本
            k: 返回的最大结果数

        Returns:
            包含检索结果的Document列表
        """
        # 切割(BAAI/bge-m3上限为8192tokens)
        logger.debug(f"查询文本: {queries}")
        splited_queries = []
        for query in queries:
            splited_queries += _split_text_by_tokens(query, self.tokenizer, max_tokens=8192, overlap=100)
        logger.debug(f"分割后的查询: {splited_queries}")
        results = self.hippo.retrieve(queries=splited_queries, num_to_retrieve=k)
        # make ruff happy
        assert isinstance(results, list)
        docs = [doc for result in results for doc in result.docs]
        # 去重
        return list(set(docs))


def _split_text_by_tokens(
    text: str, tokenizer: PreTrainedTokenizer | PreTrainedTokenizerFast, max_tokens=8192, overlap=100
) -> list[str]:
    """
    按照指定的最大 token 数量和重叠数量将文本分割成多个块
    Args:
        text: 要分割的文本
        tokenizer: 用于分割文本的分词器
        max_tokens: 每个块的最大 token 数量
        overlap: 重叠的 token 数量
    Returns:
        分割后的文本块列表
    """
    tokens = tokenizer.encode(text, add_special_tokens=False)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        start += max_tokens - overlap
    return chunks
