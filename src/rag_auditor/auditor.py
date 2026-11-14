"""Fixed-length chunking and a chunk-ending check for policy documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ChunkAuditReport:
    total_chunks: int
    broken_clauses: int
    avg_chars: float


def chunk_text(text: str, max_chars: int = 300, overlap: int = 40) -> List[str]:
    if max_chars <= overlap:
        raise ValueError("max_chars must be greater than overlap")
    chunks: List[str] = []
    start = 0
    step = max_chars - overlap
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += step
    return chunks


def audit_chunks(chunks: List[str]) -> ChunkAuditReport:
    """Counts chunks whose stripped text does not end with an accepted sentence ending."""
    broken = 0
    for ch in chunks:
        stripped = ch.strip()
        if not stripped:
            continue
        # Flag if chunk ends mid-clause without Japanese sentence ending or closes mid-article
        if not stripped.endswith(("。", "）", "」", "\n")) and not re.search(r"第\d+条$", stripped):
            broken += 1
    avg = round(sum(len(c) for c in chunks) / len(chunks), 1) if chunks else 0.0
    return ChunkAuditReport(total_chunks=len(chunks), broken_clauses=broken, avg_chars=avg)
