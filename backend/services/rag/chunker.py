"""Recursive parent-child chunking with stable document-scoped IDs."""

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .config import config


def _count_tokens_approx(text: str) -> int:
    arabic_chars = sum(1 for char in text if "\u0600" <= char <= "\u06ff")
    non_arabic_chars = len(text) - arabic_chars
    return max(1, int(arabic_chars / 2 + non_arabic_chars / 4))


@dataclass
class Chunk:
    id: str
    text: str
    metadata: Dict[str, Any]
    parent_id: Optional[str] = None
    token_count: int = 0

    def __post_init__(self) -> None:
        if self.token_count <= 0:
            self.token_count = _count_tokens_approx(self.text)


def _document_identity(metadata: Dict[str, Any]) -> str:
    article_id = str(metadata.get("article_id") or "").strip()
    if article_id:
        return article_id

    law = str(metadata.get("law") or "unknown-law").strip()
    article_number = str(metadata.get("article_number") or "unknown-article").strip()
    source_file = str(metadata.get("source_file") or "unknown-source").strip()
    language = str(metadata.get("language") or "unknown-language").strip()
    return f"{law}|{article_number}|{source_file}|{language}"


def _generate_chunk_id(
    text: str,
    index: int,
    metadata: Dict[str, Any],
    parent_id: Optional[str] = None,
) -> str:
    content = "\x1f".join(
        [
            _document_identity(metadata),
            parent_id or "",
            str(index),
            text,
        ]
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


def _validate_chunk_parameters(chunk_size: int, chunk_overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")


def recursive_chunk(
    text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    separators: Optional[List[str]] = None,
) -> List[str]:
    chunk_size = config.chunking.chunk_size if chunk_size is None else chunk_size
    chunk_overlap = (
        config.chunking.chunk_overlap if chunk_overlap is None else chunk_overlap
    )
    separators = config.chunking.separators if separators is None else separators

    _validate_chunk_parameters(chunk_size, chunk_overlap)

    cleaned = text.strip()
    if not cleaned:
        return []
    if _count_tokens_approx(cleaned) <= chunk_size:
        return [cleaned]

    for separator in separators:
        if not separator or separator not in cleaned:
            continue

        parts = [part.strip() for part in cleaned.split(separator) if part.strip()]
        if len(parts) <= 1:
            continue

        result: List[str] = []
        current = ""

        for part in parts:
            if _count_tokens_approx(part) > chunk_size:
                if current:
                    result.append(current.strip())
                    current = ""
                result.extend(
                    recursive_chunk(part, chunk_size, chunk_overlap, separators)
                )
                continue

            candidate = f"{current}{separator}{part}" if current else part
            if _count_tokens_approx(candidate) <= chunk_size:
                current = candidate
                continue

            if current:
                result.append(current.strip())
                overlap_text = _get_overlap_text(current, chunk_overlap)
                current = (
                    f"{overlap_text}{separator}{part}" if overlap_text else part
                )
            else:
                current = part

        if current:
            result.append(current.strip())

        if result:
            return result

    return _hard_split(cleaned, chunk_size, chunk_overlap)


def _get_overlap_text(text: str, overlap_tokens: int) -> str:
    if not text or overlap_tokens <= 0:
        return ""

    approximate_chars = overlap_tokens * 3
    if len(text) <= approximate_chars:
        return text.strip()

    start = max(0, len(text) - approximate_chars)
    tail = text[start:]
    boundary = re.search(r"\s", tail)
    if boundary:
        tail = tail[boundary.end() :]
    return tail.strip()


def _hard_split(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    _validate_chunk_parameters(chunk_size, chunk_overlap)

    char_limit = max(1, chunk_size * 3)
    overlap_chars = chunk_overlap * 3
    step = char_limit - overlap_chars
    if step <= 0:
        raise ValueError("Invalid hard-split step; overlap must be smaller than size")

    chunks: List[str] = []
    start = 0

    while start < len(text):
        raw_end = min(len(text), start + char_limit)
        end = raw_end

        if raw_end < len(text):
            boundary = max(
                text.rfind("\n", start + 1, raw_end),
                text.rfind(". ", start + 1, raw_end),
                text.rfind(" ", start + 1, raw_end),
            )
            if boundary > start:
                end = boundary + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = max(start + 1, end - overlap_chars)
        if next_start <= start:
            next_start = start + step
        start = next_start

    return chunks


def create_parent_child_chunks(
    text: str,
    metadata: Dict[str, Any],
    child_size: Optional[int] = None,
    parent_size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[Chunk]:
    child_size = config.chunking.chunk_size if child_size is None else child_size
    parent_size = (
        config.chunking.parent_chunk_size if parent_size is None else parent_size
    )
    overlap = config.chunking.chunk_overlap if overlap is None else overlap

    _validate_chunk_parameters(child_size, overlap)
    _validate_chunk_parameters(parent_size, overlap)
    if parent_size <= child_size:
        raise ValueError("parent_chunk_size must be greater than child chunk_size")

    chunks: List[Chunk] = []
    parent_texts = recursive_chunk(text, parent_size, overlap)

    for parent_index, parent_text in enumerate(parent_texts):
        parent_metadata = {
            **metadata,
            "chunk_type": "parent",
            "chunk_index": parent_index,
        }
        parent_id = _generate_chunk_id(
            parent_text,
            parent_index,
            parent_metadata,
        )
        chunks.append(
            Chunk(
                id=parent_id,
                text=parent_text,
                metadata=parent_metadata,
            )
        )

        child_texts = recursive_chunk(parent_text, child_size, overlap)
        for child_index, child_text in enumerate(child_texts):
            if child_text.strip() == parent_text.strip():
                continue

            child_metadata = {
                **metadata,
                "chunk_type": "child",
                "parent_id": parent_id,
                "chunk_index": child_index,
            }
            child_id = _generate_chunk_id(
                child_text,
                child_index,
                child_metadata,
                parent_id=parent_id,
            )
            chunks.append(
                Chunk(
                    id=child_id,
                    text=child_text,
                    metadata=child_metadata,
                    parent_id=parent_id,
                )
            )

    return chunks


def _language_documents(article: Dict[str, Any]) -> List[tuple[str, str]]:
    documents: List[tuple[str, str]] = []
    text_ar = str(article.get("text_ar") or "").strip()
    text_en = str(article.get("text_en") or "").strip()
    fallback = str(article.get("text") or "").strip()

    if text_ar:
        documents.append(("ar", text_ar))
    if text_en:
        documents.append(("en", text_en))
    if not documents and fallback:
        documents.append((str(article.get("language") or "und"), fallback))

    return documents


def chunk_article(article: Dict[str, Any]) -> List[Chunk]:
    all_chunks: List[Chunk] = []

    for language, text in _language_documents(article):
        metadata: Dict[str, Any] = {
            "article_id": article.get("article_id", ""),
            "article_number": str(article.get("article_number") or "Unknown"),
            "law": str(article.get("law") or "Unknown"),
            "crime_type": str(article.get("crime_type") or "general"),
            "source_file": str(article.get("source_file") or ""),
            "summary": (
                article.get("summary")
                or article.get("title_ar")
                or article.get("title_en")
                or ""
            ),
            "keywords": article.get("keywords") or [],
            "penalty_ar": article.get("penalty_ar") or "",
            "language": language,
        }
        all_chunks.extend(create_parent_child_chunks(text, metadata))

    return all_chunks
#end