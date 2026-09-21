from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any, Sequence
import uuid

from orca.schemas.orca_contract import utc_now


@dataclass(frozen=True)
class AdvisoryChunk:
    """Strongly-typed deterministic chunk of a parent marine advisory."""

    chunk_id: str
    advisory_id: uuid.UUID
    chunk_index: int
    title: str
    content: str
    language: str = "en"
    sector: str | None = None
    source_id: str = "incois_advisory"
    published_at: datetime = field(default_factory=utc_now)
    retrieved_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    unit_count: int = 0
    segmentation_method: str = "unicode_word_segmentation"


class DeterministicAdvisoryChunker:
    """Deterministic chunker preserving paragraphs, sentence boundaries, and metadata.

    Guarantees:
    - Same input always produces identical chunk boundaries, chunk_index, and chunk_id.
    - Uses BGE-M3 tokenizer when available in the environment; otherwise uses
      deterministic Unicode-aware word segmentation without guessing fake tokens.
    - Target window: 250-400 units with ~50 unit overlap.
    - Zero LLM dependencies.
    """

    def __init__(
        self,
        target_window: int = 300,
        overlap: int = 50,
        tokenizer: Any | None = None,
    ) -> None:
        self.target_window = target_window
        self.overlap = overlap
        self._tokenizer = tokenizer
        self._segmentation_method = "bge_m3_tokenizer" if tokenizer is not None else "unicode_word_segmentation"

        if self._tokenizer is None:
            # Try loading BGE-M3 tokenizer without downloading if cached
            try:
                from transformers import AutoTokenizer
                self._tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3", local_files_only=True)
                self._segmentation_method = "bge_m3_tokenizer"
            except Exception:
                self._tokenizer = None
                self._segmentation_method = "unicode_word_segmentation"

    @property
    def segmentation_method(self) -> str:
        return self._segmentation_method

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into logical sentences while preserving structure."""
        # Split by paragraph first
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        sentences: list[str] = []
        for p in paragraphs:
            # Split paragraph into sentence-like clauses
            raw_sents = re.split(r"(?<=[.!?।॥])\s+", p)
            for s in raw_sents:
                clean = s.strip()
                if clean:
                    sentences.append(clean)
        return sentences

    def _count_units(self, text: str) -> int:
        if self._tokenizer is not None:
            return len(self._tokenizer.encode(text, add_special_tokens=False))
        # Deterministic Unicode-aware word tokens
        return len(re.findall(r"\S+", text))

    def chunk_advisory(
        self,
        advisory_id: uuid.UUID,
        title: str,
        content: str,
        *,
        language: str = "en",
        sector: str | None = None,
        source_id: str = "incois_advisory",
        published_at: datetime | None = None,
        retrieved_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[AdvisoryChunk]:
        """Split an advisory into deterministic chunks with parent-child linkage."""
        clean_title = title.strip()
        clean_content = content.strip()
        pub_dt = published_at or utc_now()
        ret_dt = retrieved_at or utc_now()
        meta = metadata or {}

        sentences = self._split_into_sentences(clean_content)
        if not sentences:
            # Return single empty or title-only chunk
            chunk_id = f"{advisory_id}_chunk_0"
            return [
                AdvisoryChunk(
                    chunk_id=chunk_id,
                    advisory_id=advisory_id,
                    chunk_index=0,
                    title=clean_title,
                    content=clean_content or clean_title,
                    language=language,
                    sector=sector,
                    source_id=source_id,
                    published_at=pub_dt,
                    retrieved_at=ret_dt,
                    metadata=dict(meta),
                    unit_count=self._count_units(clean_content or clean_title),
                    segmentation_method=self._segmentation_method,
                )
            ]

        # Group sentences into windows of target_window with overlap
        chunks: list[AdvisoryChunk] = []
        sentence_data = [(s, self._count_units(s)) for s in sentences]

        i = 0
        chunk_idx = 0
        total_sents = len(sentence_data)

        while i < total_sents:
            current_sents: list[str] = []
            current_count = 0
            start_i = i

            while i < total_sents:
                s_text, s_count = sentence_data[i]
                if current_count + s_count > self.target_window and current_sents:
                    break
                current_sents.append(s_text)
                current_count += s_count
                i += 1

            chunk_text = " ".join(current_sents)
            chunk_id = f"{advisory_id}_chunk_{chunk_idx}"
            chunks.append(
                AdvisoryChunk(
                    chunk_id=chunk_id,
                    advisory_id=advisory_id,
                    chunk_index=chunk_idx,
                    title=clean_title,
                    content=chunk_text,
                    language=language,
                    sector=sector,
                    source_id=source_id,
                    published_at=pub_dt,
                    retrieved_at=ret_dt,
                    metadata=dict(meta),
                    unit_count=current_count,
                    segmentation_method=self._segmentation_method,
                )
            )
            chunk_idx += 1

            if i >= total_sents:
                break

            # Calculate rewind for overlap
            overlap_count = 0
            rewind_i = i
            while rewind_i > start_i + 1:
                overlap_count += sentence_data[rewind_i - 1][1]
                if overlap_count >= self.overlap:
                    break
                rewind_i -= 1

            i = rewind_i

        return chunks
