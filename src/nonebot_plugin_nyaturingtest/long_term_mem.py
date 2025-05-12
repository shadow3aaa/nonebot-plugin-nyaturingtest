from datetime import datetime, timedelta
from math import exp, log1p, sqrt
import os
import uuid

import faiss  # Facebook AI Similarity Search 库 :contentReference[oaicite:0]{index=0}
from langchain_community.docstore.in_memory import (
    InMemoryDocstore,
)  # FAISS 默认的 docstore 实现 :contentReference[oaicite:2]{index=2}
from langchain_community.vectorstores.faiss import (
    FAISS,
)  # LangChain Community 封装 :contentReference[oaicite:1]{index=1}
from langchain_core.documents import Document
from nonebot import logger
from requests.exceptions import HTTPError

from .siliconflow_embeddings import SiliconFlowEmbeddings


class LongTermMemory:
    def __init__(
        self,
        embedding_api_key: str,
        persist_directory: str = "./faiss_index",
        index_filename: str = "index.faiss",
        model: str = "BAAI/bge-large-zh-v1.5",
        dimension: int = 1024,  # 嵌入向量维度，需与你的模型输出维度一致
    ):
        # 嵌入模型
        self.embeddings = SiliconFlowEmbeddings(api_key=embedding_api_key, model=model)

        # 持久化目录与文件名
        os.makedirs(persist_directory, exist_ok=True)
        self.persist_directory = persist_directory
        self.index_path = os.path.join(persist_directory, index_filename)

        # 尝试加载已有索引，允许危险反序列化 pickle（可信源）:contentReference[oaicite:6]{index=6}
        try:
            self.vectorstore = FAISS.load_local(
                folder_path=persist_directory,
                embeddings=self.embeddings,
                index_name=index_filename,
                allow_dangerous_deserialization=True,
            )
        except Exception as e:
            logger.warning(f"[Warn] Failed to load FAISS index: {e}")
            # 加载失败：手动创建真正空索引，不调用任何 embed_* 方法
            index = faiss.IndexFlatL2(dimension)  # L2 距离精确搜索 :contentReference[oaicite:7]{index=7}
            docstore = InMemoryDocstore()  # 空的内存 docstore :contentReference[oaicite:8]{index=8}
            index_to_docstore_id = {}  # 索引到文档 ID 的映射
            # 直接调用 FAISS 构造函数，跳过 from_* classmethod
            self.vectorstore = FAISS(
                embedding_function=self.embeddings,
                index=index,
                docstore=docstore,
                index_to_docstore_id=index_to_docstore_id,
            )

        self._last_forget = datetime.now()

    def _now_str(self) -> str:
        return datetime.now().isoformat()

    def save(self):
        """持久化 FAISS 索引和 docstore 到本地文件夹。"""
        self.vectorstore.save_local(folder_path=self.persist_directory, index_name=os.path.basename(self.index_path))

    def add_texts(
        self, texts: list[str], metadatas: list[dict] | None = None, similarity_threshold: float = 0.85
    ) -> None:
        """
        添加文本到长期记忆，带语义去重功能

        Args:
            texts: 要添加的文本列表
            metadatas: 元数据列表，可选
            similarity_threshold: 相似度阈值，超过此值则认为是重复内容，范围[0-1]，默认0.85
        """
        if not texts:
            return

        # 准备要添加的文本和元数据
        filtered_texts = []
        filtered_metadatas = []

        now = self._now_str()

        # 为每个文本检查重复并过滤
        for i, text in enumerate(texts):
            # 跳过空文本
            if not text.strip():
                continue

            # 检查是否存在相似文本
            is_duplicate = False

            try:
                # 搜索相似文本
                similar_docs = self.vectorstore.similarity_search_with_score(text, k=1)

                # 如果找到结果且相似度高于阈值，则认为是重复
                if similar_docs and similar_docs[0][1] <= (1.0 - similarity_threshold):
                    is_duplicate = True
                    # 如果有元数据，检查是否需要合并
                    if metadatas is not None and i < len(metadatas):
                        doc_id = similar_docs[0][0].metadata.get("doc_id")
                        if doc_id:
                            # 获取已存在文档的元数据
                            existing_doc = similar_docs[0][0]
                            existing_meta = existing_doc.metadata
                            current_meta = metadatas[i]

                            # 合并元数据，相同条目用' | '隔开
                            merged_meta = existing_meta.copy()

                            for key, value in current_meta.items():
                                if key in merged_meta and key not in [
                                    "doc_id",
                                    "timestamp",
                                    "last_access",
                                    "access_count",
                                ]:
                                    if str(value) != str(merged_meta[key]):
                                        merged_meta[key] = f"{merged_meta[key]} | {value}"
                                elif key not in ["doc_id", "timestamp", "last_access", "access_count"]:
                                    merged_meta[key] = value

                            # 更新文档元数据
                            self.vectorstore.delete(ids=[doc_id])
                            self.vectorstore.add_texts(
                                texts=[existing_doc.page_content], metadatas=[merged_meta], ids=[doc_id]
                            )
                            logger.debug(f"合并重复文本元数据: '{text[:30]}...' 相似度: {1.0 - similar_docs[0][1]:.2f}")
                        else:
                            logger.debug(f"跳过添加重复文本: '{text[:30]}...' 相似度: {1.0 - similar_docs[0][1]:.2f}")
                    else:
                        logger.debug(f"跳过添加重复文本: '{text[:30]}...' 相似度: {1.0 - similar_docs[0][1]:.2f}")
            except Exception as e:
                logger.debug(f"检查相似文本失败: {e}")

            if not is_duplicate:
                filtered_texts.append(text)
                # 如果有元数据，则保留对应的元数据
                if metadatas is not None and i < len(metadatas):
                    filtered_metadatas.append(metadatas[i])

        # 如果所有文本都被过滤掉了，直接返回
        if not filtered_texts:
            return

        # 生成UUID和基础元数据
        ids = [str(uuid.uuid4()) for _ in filtered_texts]
        base_metadatas = [{"doc_id": id_, "timestamp": now, "last_access": now, "access_count": 0} for id_ in ids]

        if metadatas is not None and filtered_metadatas:
            if len(filtered_metadatas) != len(filtered_texts):
                raise ValueError("Length of filtered_metadatas must match length of filtered_texts.")
            merged_metadatas = [{**base, **user} for base, user in zip(base_metadatas, filtered_metadatas)]
        else:
            merged_metadatas = base_metadatas

        try:
            self.vectorstore.add_texts(texts=filtered_texts, metadatas=merged_metadatas, ids=ids)
            logger.debug(f"添加了 {len(filtered_texts)} 条非重复文本到长期记忆")
        except HTTPError as e:
            logger.warning(f"Embedding failed ({e.response.status_code}): {e.response.text}")
        self.save()

    def retrieve(self, query: str, k: int = 5) -> list[Document]:
        self._maybe_prune()
        docs = self.vectorstore.similarity_search(query, k=k)
        self._update_metadata(docs)
        self.save()
        return docs

    def _update_metadata(self, docs: list[Document]):
        now = self._now_str()
        updated_docs = []
        delete_ids = []
        for doc in docs:
            meta = doc.metadata
            doc_id = meta.get("doc_id")
            if not doc_id:
                logger.warning("Document missing doc_id; skipping metadata update.")
                continue
            meta["last_access"] = now
            meta["access_count"] = meta.get("access_count", 0) + 1
            delete_ids.append(doc_id)
            updated_docs.append(Document(page_content=doc.page_content, metadata=meta))
        if delete_ids:
            self.vectorstore.delete(ids=delete_ids)
        if updated_docs:
            self.vectorstore.add_documents(updated_docs, ids=delete_ids)
        self.save()

    def clear(self) -> None:
        docs_map = getattr(self.vectorstore.docstore, "_dict", None)
        if not isinstance(docs_map, dict):
            return
        ids = [doc.metadata.get("doc_id") for doc in docs_map.values() if doc.metadata.get("doc_id")]
        if ids:
            self.vectorstore.delete(ids=ids)
            self.save()

    def list_all(self) -> list[Document]:
        """
        列出所有存储在 FAISS 内存 Docstore 中的 Document 对象，
        包含 id、page_content 和 metadata。
        """
        # 直接访问 InMemoryDocstore 的私有 _dict
        # key: doc_id, value: Document
        docs_map = getattr(self.vectorstore.docstore, "_dict", None)
        logger.debug(f"InMemoryDocstore _dict: {docs_map}")
        if docs_map is None:
            # 容错：如果未来实现改变了属性名，再退回空列表
            logger.warning("InMemoryDocstore _dict not found, returning empty list.")
            return []
        return list(docs_map.values())

    def prune_forgettable(self, base_decay_hours: float = 24, threshold: float = 0.01) -> None:
        now = datetime.now()
        to_delete = []
        docstore = getattr(self.vectorstore.docstore, "_dict", None)
        if not isinstance(docstore, dict):
            return
        for doc in docstore.values():
            meta = doc.metadata
            doc_id = meta.get("doc_id")
            if not doc_id:
                continue  # 跳过无法识别的文档
            last = meta.get("last_access") or meta.get("timestamp")
            first = meta.get("timestamp") or last
            try:
                last_dt = datetime.fromisoformat(last)
                first_dt = datetime.fromisoformat(first)
            except ValueError:
                continue
            retention = exp(
                -sqrt((now - last_dt).total_seconds() / 3600)
                / (
                    base_decay_hours
                    * (1 + meta.get("access_count", 0))
                    * log1p((now - first_dt).total_seconds() / 3600)
                )
            )
            if retention < threshold:
                to_delete.append(doc_id)
        if to_delete:
            self.vectorstore.delete(ids=to_delete)
            self.save()

    def _maybe_prune(self):
        if datetime.now() - self._last_forget > timedelta(hours=1):
            self.prune_forgettable()
            self._last_forget = datetime.now()
