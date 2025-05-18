from collections.abc import Awaitable, Callable
from datetime import datetime
import os
import shutil

from hipporag import HippoRAG
from nonebot import logger
import numpy as np
from transformers.models.auto.tokenization_auto import AutoTokenizer

from .siliconflow_embeddings import SiliconFlowEmbeddings


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
        self._tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3", trust_remote_code=True)
        # 初始化嵌入模型，用于计算是否需要重新检索
        self._embedding_model = SiliconFlowEmbeddings(
            model="BAAI/bge-m3",
            api_key=embedding_api_key,
        )
        self._docs = []
        self._cosine_similarity = 0.0

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
        # 删除内存缓存
        self._docs.clear()
        self._cosine_similarity = 0.0
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

    def add_text(self, text: str):
        """
        添加文本到缓存

        Args:
            text: 要添加的文本
        """
        self._cache += text + "\n"

    def add_texts(self, texts: list[str]):
        """
        添加文本到缓存

        Args:
            texts: 要添加的文本列表
        """
        for text in texts:
            self.add_text(text)

    def _index(self):
        """
        对缓存的文本进行索引，整理到长期记忆
        """
        if self._cache:
            texts = _split_text_by_tokens(self._cache, self._tokenizer, max_tokens=512, overlap=100)
            texts_list = _split_texts_by_byte_limit(texts, max_bytes=30_000)
            for texts in texts_list:
                total_bytes = sum(len(" ".join(batch).encode()) for batch in texts_list)
                logger.debug(f"索引文本总大小: {total_bytes / 1024:.2f} KB")
                self.hippo.index(texts)
            logger.info(f"已索引 {len(texts)} 条缓存文本")
            self._cache = ""
        else:
            logger.info("没有缓存的文本需要索引")

    async def retrieve(self, queries: list[str], k: int = 5) -> list[str]:
        """
        检索与查询相关的文本

        Args:
            query: 查询文本
            k: 返回的最大结果数

        Returns:
            包含检索结果的Document列表
        """
        # 检查是否需要重新检索
        if not await self._need_retrieve(queries):
            logger.info("不需要重新检索")
            return self._docs

        # 重新索引
        self._index()

        # 切割(BAAI/bge-m3上限为8192tokens)
        logger.debug(f"查询文本: {queries}")
        splited_queries = []
        for query in queries:
            splited_queries += _split_text_by_tokens(query, self._tokenizer, max_tokens=8192, overlap=100)
        logger.debug(f"分割后的查询: {splited_queries}")
        query_batches = _split_texts_by_byte_limit(splited_queries, max_bytes=30_000)

        all_docs: set[str] = set()
        for batch in query_batches:
            results = self.hippo.retrieve(queries=batch, num_to_retrieve=k)
            # make ruff happy
            assert isinstance(results, list)
            docs = [doc for result in results for doc in result.docs]
            all_docs.update(docs)

        self._docs = list(all_docs)
        self._cosine_similarity = await _cosine_similarity(queries, self._docs, self._embedding_model.embed_documents)

        # 去重
        return self._docs

    async def _need_retrieve(self, new_queries: list[str], scale: float = 0.8) -> bool:
        """
        Arguments:
            new_queries: 新的查询文本
            scale: 触发重新检索的余弦相似度比例的阈值，如0.8代表相似度不如原来的80%则重新检索
        判断是否需要重新检索
        """

        if not self._docs or self._cosine_similarity == 0.0:
            return True
        current_similarity = await _cosine_similarity(new_queries, self._docs, self._embedding_model.embed_documents)

        logger.debug(f"当前余弦相似度: {current_similarity}")
        logger.debug(f"原余弦相似度: {self._cosine_similarity}")
        logger.debug(f"触发比例: {scale}, 当前比例: {current_similarity / self._cosine_similarity}")

        return current_similarity < scale * self._cosine_similarity


async def _cosine_similarity(
    a: list[str], b: list[str], embed: Callable[[list[str]], Awaitable[list[list[float]]]]
) -> float:
    """
    计算两个字符串列表之间的整体余弦相似度
    Args:
        a: 第一个字符串列表
        b: 第二个字符串列表
    Returns:
        余弦相似度值
    """
    # 向量化
    a_vecs = np.array(await embed(a))
    b_vecs = np.array(await embed(b))
    # 计算平均向量
    a_mean = np.mean(a_vecs, axis=0)
    b_mean = np.mean(b_vecs, axis=0)
    return _cosine(a_mean, b_mean)


def _cosine(a, b) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)


def _split_text_by_tokens(text: str, tokenizer, max_tokens=8192, overlap=100) -> list[str]:
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
    tokens = tokenizer.encode(text, add_special_tokens=False, truncation=True)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        start += max_tokens - overlap
    return chunks


def _split_texts_by_byte_limit(texts: list[str], max_bytes: int = 30_000) -> list[list[str]]:
    """
    将字符串列表按 UTF-8 编码字节大小切割为多个批次，每批总字节数不超过 max_bytes。

    参数:
        texts (list[str]): 要切割的文本列表。
        max_bytes (int): 每个批次最大字节数（默认为 30,000 字节）。

    返回:
        list[list[str]]: 切割后的文本批次列表。
    """
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_bytes: int = 0

    for text in texts:
        text_bytes = len(text.encode("utf-8"))

        if text_bytes > max_bytes:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_bytes = 0
            batches.append([text])
            continue

        if current_bytes + text_bytes <= max_bytes:
            current_batch.append(text)
            current_bytes += text_bytes
        else:
            batches.append(current_batch)
            current_batch = [text]
            current_bytes = text_bytes

    if current_batch:
        batches.append(current_batch)

    return batches
