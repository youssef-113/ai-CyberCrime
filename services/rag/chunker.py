"""Recursive Chunking with Parent-Child Strategy

Production chunking: recursive splitting with ~512 tokens / ~200 token overlap.
Parent-child: embed small chunks, return larger parent sections for context.
"""
import re
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass

from .config import config


def _count_tokens_approx(text: str) -> int:
    """Approximate token count (1 token ≈ 4 chars for English, ~2 chars for Arabic)."""
    # Blend heuristic: average between English and Arabic ratio
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    non_arabic_chars = len(text) - arabic_chars
    return max(1, int(arabic_chars / 2 + non_arabic_chars / 4))


@dataclass
class Chunk:
    """A single chunk with metadata."""
    id: str
    text: str
    metadata: Dict
    parent_id: Optional[str] = None
    token_count: int = 0

    def __post_init__(self):
        if self.token_count == 0:
            self.token_count = _count_tokens_approx(self.text)


def _generate_chunk_id(text: str, index: int, parent_id: Optional[str] = None) -> str:
    """Content-addressable chunk ID using hash of text + index."""
    content = f"{parent_id or ''}:{index}:{text[:200]}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def _split_by_separators(text: str, separators: List[str]) -> List[str]:
    """Split text by separators in priority order."""
    if not text.strip():
        return []

    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) > 1:
                return parts

    return [text.strip()]


def recursive_chunk(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    separators: List[str] = None,
) -> List[str]:
    """Recursive chunking that respects document structure.

    Splits by highest-priority separator first, then recursively
    splits any chunk that exceeds chunk_size.
    """
    chunk_size = chunk_size or config.chunking.chunk_size
    chunk_overlap = chunk_overlap or config.chunking.chunk_overlap
    separators = separators or config.chunking.separators

    if _count_tokens_approx(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    # Try splitting by each separator
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            parts = [p.strip() for p in parts if p.strip()]

            if not parts:
                continue

            # Merge small parts and split large ones
            result = []
            current_chunk = ""

            for part in parts:
                part_tokens = _count_tokens_approx(part)

                if part_tokens > chunk_size:
                    # Part is too large, recurse
                    if current_chunk:
                        result.append(current_chunk)
                        current_chunk = ""
                    sub_chunks = recursive_chunk(part, chunk_size, chunk_overlap, separators)
                    result.extend(sub_chunks)
                elif _count_tokens_approx(current_chunk + sep + part) > chunk_size:
                    # Adding this part would exceed limit
                    if current_chunk:
                        result.append(current_chunk)
                    # Start new chunk with overlap
                    overlap_text = _get_overlap_text(current_chunk, chunk_overlap)
                    current_chunk = overlap_text + sep + part if overlap_text else part
                else:
                    current_chunk = current_chunk + sep + part if current_chunk else part

            if current_chunk:
                result.append(current_chunk)

            if result:
                return result

    # No separator worked, hard split by character count
    return _hard_split(text, chunk_size, chunk_overlap)


def _get_overlap_text(text: str, overlap_tokens: int) -> str:
    """Get the tail of text that represents overlap_tokens worth of content."""
    if not text:
        return ""
    # Approximate: overlap_tokens * 3 chars (average)
    char_count = overlap_tokens * 3
    if len(text) <= char_count:
        return text
    return text[-char_count:]


def _hard_split(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Hard split by character count when no separators work."""
    char_per_token = 3  # approximate
    char_limit = chunk_size * char_per_token
    overlap_chars = chunk_overlap * char_per_token

    chunks = []
    start = 0
    while start < len(text):
        end = start + char_limit
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap_chars

    return chunks


def create_parent_child_chunks(
    text: str,
    metadata: Dict,
    child_size: int = None,
    parent_size: int = None,
    overlap: int = None,
) -> List[Chunk]:
    """Create parent-child chunks.

    Parent chunks: larger sections for context retrieval.
    Child chunks: smaller sections for precise embedding/matching.
    Each child points to its parent so the full context can be returned.
    """
    child_size = child_size or config.chunking.chunk_size
    parent_size = parent_size or config.chunking.parent_chunk_size
    overlap = overlap or config.chunking.chunk_overlap

    # First, create parent chunks
    parent_texts = recursive_chunk(text, parent_size, overlap)
    chunks = []

    for p_idx, parent_text in enumerate(parent_texts):
        parent_id = _generate_chunk_id(parent_text, p_idx)
        parent_chunk = Chunk(
            id=parent_id,
            text=parent_text,
            metadata={
                **metadata,
                "chunk_type": "parent",
                "chunk_index": p_idx,
            },
            parent_id=None,
        )
        chunks.append(parent_chunk)

        # Create child chunks within this parent
        child_texts = recursive_chunk(parent_text, child_size, overlap)
        for c_idx, child_text in enumerate(child_texts):
            child_id = _generate_chunk_id(child_text, c_idx, parent_id)
            child_chunk = Chunk(
                id=child_id,
                text=child_text,
                metadata={
                    **metadata,
                    "chunk_type": "child",
                    "parent_id": parent_id,
                    "chunk_index": c_idx,
                },
                parent_id=parent_id,
            )
            chunks.append(child_chunk)

    return chunks


def chunk_article(article: Dict) -> List[Chunk]:
    """Chunk a single law article with rich metadata.

    Each chunk includes:
    - Summary (from article title)
    - Keywords
    - Source document info
    - Parent-child relationships
    """
    text = article.get("text_ar", "") or article.get("text_en", "") or article.get("text", "")
    if not text:
        return []

    base_metadata = {
        "article_number": article.get("article_number", "Unknown"),
        "law": article.get("law", "Unknown"),
        "crime_type": article.get("crime_type", "general"),
        "source_file": article.get("source_file", ""),
        "summary": article.get("title_ar", "") or article.get("title_en", "") or "",
        "keywords": article.get("keywords", []),
        "penalty_ar": article.get("penalty_ar", ""),
    }

    return create_parent_child_chunks(text, base_metadata)
