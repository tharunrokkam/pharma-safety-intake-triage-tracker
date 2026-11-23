"""Token-aware chunking: 512-token chunks with 64-token overlap, measured with the encoder's tokenizer."""
from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS

_APPROX_TOKEN = re.compile(r"\w+|[^\w\s]")


def approx_token_len(text: str) -> int:
    """Fallback token counter (word-piece-like) used when the HF tokenizer is not available."""
    return len(_APPROX_TOKEN.findall(text))


def make_splitter(tokenizer: Any | None = None) -> RecursiveCharacterTextSplitter:
    if tokenizer is not None:
        return RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
            tokenizer, chunk_size=CHUNK_SIZE_TOKENS, chunk_overlap=CHUNK_OVERLAP_TOKENS)
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS, chunk_overlap=CHUNK_OVERLAP_TOKENS, length_function=approx_token_len)


def chunk_documents(docs: list[Document], splitter: RecursiveCharacterTextSplitter) -> list[Document]:
    """Split and assign stable chunk ids '<doc_id>#<n>' (section-level docs get a section suffix)."""
    out: list[Document] = []
    counters: dict[str, int] = {}
    for doc in docs:
        for piece in splitter.split_documents([doc]):
            base = doc.metadata.get("doc_id", "DOC")
            key = f"{base}|{doc.metadata.get('section', '')}"
            n = counters.get(key, 0)
            counters[key] = n + 1
            section = doc.metadata.get("section")
            sec_tag = re.sub(r"[^A-Za-z0-9]+", "", section.split(" ")[0]) if section else ""
            chunk_id = f"{base}{'/' + sec_tag if sec_tag else ''}#{n}"
            piece.metadata = {**doc.metadata, "chunk_id": chunk_id}
            piece.id = chunk_id
            out.append(piece)
    return out
