"""Paragraph-aware chunking with exact source offsets.

Splits an artifact body into chunks on blank lines, packing consecutive paragraphs up to
`max_chars`. Offsets are exact: `text[chunk.char_start:chunk.char_end] == chunk.text`, so
chunk-level citations can later be refined to character spans for free (schema decision D5).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    char_start: int
    char_end: int


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) spans of non-blank paragraphs, separated by blank lines."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for block in text.split("\n\n"):
        start = text.index(block, pos) if block else pos
        end = start + len(block)
        pos = end
        if block.strip():
            spans.append((start, end))
    return spans


def chunk_text(text: str, max_chars: int = 800) -> list[Chunk]:
    """Pack paragraphs into chunks of up to ~max_chars, preserving exact offsets.

    A single paragraph longer than max_chars becomes its own chunk (we do not split
    mid-paragraph). Returns at least one chunk for any non-empty text.
    """
    spans = _paragraph_spans(text)
    if not spans:
        return []

    chunks: list[Chunk] = []
    ordinal = 0
    cur_start, cur_end = spans[0]

    for start, end in spans[1:]:
        # Extending to `end` keeps us within budget? then merge; else flush.
        if (end - cur_start) <= max_chars:
            cur_end = end
        else:
            chunks.append(Chunk(ordinal, text[cur_start:cur_end], cur_start, cur_end))
            ordinal += 1
            cur_start, cur_end = start, end

    chunks.append(Chunk(ordinal, text[cur_start:cur_end], cur_start, cur_end))
    return chunks
