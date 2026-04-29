from __future__ import annotations

import hashlib
import math
import re


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_+\-./]+|[\u4e00-\u9fff]")


class LocalHashEmbeddings:
    """Small deterministic local embedding model for Chroma.

    DeepSeek exposes chat/completions style model APIs, but this project still
    needs vectors for Chroma RAG. To keep every external model API call on
    DeepSeek, embeddings are generated locally instead of calling another API.
    """

    def __init__(self, dimensions: int = 384) -> None:
        if dimensions < 32:
            raise ValueError("local embedding dimensions must be >= 32")
        self.dimensions = dimensions

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = self._tokens(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], byteorder="big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _tokens(self, text: str) -> list[str]:
        raw_tokens = [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
        expanded: list[str] = []
        for token in raw_tokens:
            expanded.append(token)
            if len(token) > 3 and not self._is_cjk(token):
                expanded.extend(token[index : index + 3] for index in range(len(token) - 2))
        return expanded

    def _is_cjk(self, token: str) -> bool:
        return all("\u4e00" <= char <= "\u9fff" for char in token)
