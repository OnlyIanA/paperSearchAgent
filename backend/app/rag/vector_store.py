from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import Settings
from app.models.schemas import MemoryHit, Paper
from app.rag.local_embeddings import LocalHashEmbeddings


class ChromaRAGStore:
    """Persistent Chroma vector store for papers and long-term memories."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.persist_dir = Path(settings.chroma_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._papers = self._client.get_or_create_collection(name="paper_chunks_local_v1")
        self._memories = self._client.get_or_create_collection(name="long_term_memories_local_v1")
        self._embeddings = LocalHashEmbeddings(
            dimensions=self.settings.local_embedding_dimensions,
        )
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", "。", ". ", " ", ""],
        )

    def upsert_paper(self, paper: Paper, summary: str | None = None) -> int:
        text_parts = [
            f"标题：{paper.title}",
            f"作者：{', '.join(paper.authors)}",
            f"分类：{', '.join(paper.categories)}",
            f"摘要：{paper.abstract}",
        ]
        if summary:
            text_parts.append(f"总结：{summary}")
        text = "\n\n".join(part for part in text_parts if part.strip())
        chunks = self._splitter.split_text(text)
        if not chunks:
            return 0

        try:
            self._papers.delete(where={"arxiv_id": paper.arxiv_id})
        except Exception:
            pass

        vectors = self._embeddings.embed_documents(chunks)
        ids = [f"paper:{paper.arxiv_id}:{index}" for index, _ in enumerate(chunks)]
        metadatas = [
            {
                "type": "paper",
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "pdf_url": paper.pdf_url,
                "source_url": paper.source_url,
                "chunk_index": index,
            }
            for index, _ in enumerate(chunks)
        ]
        self._papers.upsert(ids=ids, documents=chunks, embeddings=vectors, metadatas=metadatas)
        return len(chunks)

    def add_memory(
        self,
        content: str,
        *,
        kind: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        metadata_payload = {
            "type": kind,
            "session_id": session_id or "",
            **(metadata or {}),
        }
        vector = self._embeddings.embed_query(content)
        digest = hashlib.sha256(f"{kind}:{session_id or ''}:{content}".encode("utf-8")).hexdigest()
        memory_id = f"memory:{kind}:{digest[:24]}"
        self._memories.upsert(
            ids=[memory_id],
            documents=[content],
            embeddings=[vector],
            metadatas=[metadata_payload],
        )
        return memory_id

    def retrieve(self, query: str, *, top_k: int = 5) -> list[MemoryHit]:
        query_vector = self._embeddings.embed_query(query)
        hits: list[MemoryHit] = []

        for collection in (self._papers, self._memories):
            result = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            docs = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            for doc, metadata, distance in zip(docs, metadatas, distances, strict=False):
                score = 1.0 / (1.0 + float(distance))
                hits.append(MemoryHit(content=doc, metadata=metadata or {}, score=score))

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]
