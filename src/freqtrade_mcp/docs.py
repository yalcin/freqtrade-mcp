"""Documentation reader for freqtrade markdown docs.

Provides read-only access to the freqtrade documentation files.
Loads and caches markdown content with TTL-based expiration.
"""

import logging
import os
from pathlib import Path

from freqtrade_mcp.cache import ttl_cache
from freqtrade_mcp.constants import (
    DEFAULT_DOC_MAX_CHARS,
    DOC_SEARCH_CONTEXT_LINES,
    DOC_SECTION_PREFIX,
    ENV_DOCS_PATH,
    MAX_DOC_MAX_CHARS,
    MAX_DOC_SEARCH_RESULTS,
)
from freqtrade_mcp.exceptions import DocSectionNotFoundError, DocTopicNotFoundError
from freqtrade_mcp.models import DocContent, DocSearchResult, DocTopic
from freqtrade_mcp.validators import (
    validate_doc_search_query,
    validate_doc_section,
    validate_doc_topic,
    validate_filter_string,
)

logger = logging.getLogger(__name__)

# Subdirectories to scan for markdown files
_SCAN_SUBDIRS: tuple[str, ...] = ("commands", "includes")


def _discover_docs_path() -> Path | None:
    """Discover the freqtrade documentation directory.

    Checks ``FREQTRADE_DOCS_PATH`` env var. If not set or invalid,
    returns None and logs a warning.

    Returns:
        Path to the docs directory, or None if not found.
    """
    env_path = os.environ.get(ENV_DOCS_PATH)
    if not env_path:
        logger.warning(
            "Freqtrade documentation not configured. Set %s to enable doc tools.",
            ENV_DOCS_PATH,
        )
        return None

    p = Path(env_path)
    if p.is_dir() and any(p.glob("*.md")):
        logger.info("Using documentation configured by %s", ENV_DOCS_PATH)
        return p.resolve()

    logger.warning(
        "%s is set but does not point to a directory containing markdown files.",
        ENV_DOCS_PATH,
    )
    return None


def _extract_title(content: str, filename: str) -> str:
    """Extract the H1 title from markdown content.

    Args:
        content: Full markdown content.
        filename: Filename for fallback title.

    Returns:
        The document title.
    """
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            return stripped[2:].strip()
    # Fallback: humanize filename
    stem = filename.rsplit(".", maxsplit=1)[0]
    return stem.replace("-", " ").replace("_", " ").title()


def _is_safe_path(filepath: Path, docs_root: Path) -> bool:
    """Verify that a file path is safely under the docs root.

    Args:
        filepath: The resolved file path to check.
        docs_root: The resolved docs root directory.

    Returns:
        True if the path is safely under docs_root.
    """
    try:
        filepath.resolve().relative_to(docs_root.resolve())
    except ValueError:
        return False
    return True


def _scan_directory(
    directory: Path,
    docs_root: Path,
    prefix: str = "",
) -> dict[str, tuple[str, str, int]]:
    """Scan a directory for markdown files and build index entries.

    Args:
        directory: Directory to scan.
        docs_root: Root docs directory for safety checks.
        prefix: Topic prefix (e.g., "commands/" for subdirectories).

    Returns:
        Dictionary mapping topic names to (title, content, size) tuples.
    """
    index: dict[str, tuple[str, str, int]] = {}

    if not directory.is_dir():
        return index

    for md_file in sorted(directory.glob("*.md")):
        if not md_file.is_file():
            continue
        if not _is_safe_path(md_file, docs_root):
            continue

        topic = f"{prefix}{md_file.stem}"
        try:
            content = md_file.read_text(encoding="utf-8")
            size = md_file.stat().st_size
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to read documentation topic %s: %s", topic, type(e).__name__)
            continue

        title = _extract_title(content, md_file.name)
        index[topic] = (title, content, size)

    return index


@ttl_cache()
def _load_docs_index() -> dict[str, tuple[str, str, int]] | None:
    """Load and index all documentation files.

    Returns:
        Dictionary mapping topic names to (title, content, size_bytes) tuples,
        or None if docs are not available.
    """
    docs_path = _discover_docs_path()
    if docs_path is None:
        return None

    # Scan top-level .md files
    index = _scan_directory(docs_path, docs_path)

    # Scan known subdirectories
    for subdir in _SCAN_SUBDIRS:
        subdir_path = docs_path / subdir
        sub_index = _scan_directory(subdir_path, docs_path, prefix=f"{subdir}/")
        index.update(sub_index)

    logger.info("Loaded %d documentation topics", len(index))
    return index


# --- Public API ---


def list_docs(filter_str: str | None = None) -> list[DocTopic] | None:
    """List available documentation topics.

    Args:
        filter_str: Optional filter keyword.

    Returns:
        List of DocTopic summaries, or None if docs unavailable.
    """
    validated_filter: str | None = None
    if filter_str:
        validated_filter = validate_filter_string(filter_str, label="docs filter")

    index = _load_docs_index()
    if index is None:
        return None

    topics: list[DocTopic] = []
    for topic_name, (title, _content, size) in sorted(index.items()):
        if validated_filter:
            searchable = f"{topic_name} {title}".lower()
            if validated_filter not in searchable:
                continue

        topics.append(
            DocTopic(
                topic=topic_name,
                title=title,
                path=f"{topic_name}.md",
                size_bytes=size,
            )
        )

    return topics


def search_docs(
    query: str,
    max_results: int = 10,
) -> list[DocSearchResult] | None:
    """Full-text search across all documentation.

    Args:
        query: Search query text.
        max_results: Maximum results to return.

    Returns:
        List of search results with context snippets, or None if docs unavailable.
    """
    validated_query = validate_doc_search_query(query)
    max_results = min(max_results, MAX_DOC_SEARCH_RESULTS)

    index = _load_docs_index()
    if index is None:
        return None

    query_words = validated_query.lower().split()
    if not query_words:
        return []

    results: list[DocSearchResult] = []

    for topic_name, (title, content, _size) in sorted(index.items()):
        lines = content.splitlines()
        content_lower = content.lower()

        # Quick reject: all query words must appear somewhere in the doc
        if not all(word in content_lower for word in query_words):
            continue

        # Find lines where at least one query word appears
        matching_lines: list[int] = []
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(word in line_lower for word in query_words):
                matching_lines.append(i)

        if not matching_lines:
            continue

        # Extract snippets with deduplication of overlapping context
        consumed: set[int] = set()
        for match_line in matching_lines:
            if match_line in consumed:
                continue

            start = max(0, match_line - DOC_SEARCH_CONTEXT_LINES)
            end = min(len(lines), match_line + DOC_SEARCH_CONTEXT_LINES + 1)
            snippet = "\n".join(lines[start:end])

            consumed.update(range(start, end))

            results.append(
                DocSearchResult(
                    topic=topic_name,
                    title=title,
                    line_number=match_line + 1,
                    snippet=snippet,
                )
            )

            if len(results) >= max_results:
                return results

    return results


def _list_sections(content: str) -> list[str]:
    """Collect the level-2 headings of a markdown document.

    Args:
        content: Full markdown content.

    Returns:
        Section titles in document order.
    """
    sections: list[str] = []
    for line in content.splitlines():
        if line.startswith(DOC_SECTION_PREFIX) and not line.startswith("###"):
            title = line[len(DOC_SECTION_PREFIX) :].strip()
            if title:
                sections.append(title)
    return sections


def _extract_section(content: str, section: str) -> str | None:
    """Extract one level-2 section, heading included.

    The section runs from its own heading up to the next level-1 or level-2
    heading, so nested '###' subsections stay with their parent.

    Args:
        content: Full markdown content.
        section: Section title to extract, matched case-insensitively.

    Returns:
        The section text, or None if no heading matches.
    """
    wanted = section.strip().lower()
    lines = content.splitlines()
    start: int | None = None

    for i, line in enumerate(lines):
        is_section_heading = line.startswith(DOC_SECTION_PREFIX) and not line.startswith("###")
        if start is None:
            if is_section_heading and line[len(DOC_SECTION_PREFIX) :].strip().lower() == wanted:
                start = i
        elif is_section_heading or (line.startswith("# ") and not line.startswith("##")):
            return "\n".join(lines[start:i]).rstrip()

    if start is None:
        return None
    return "\n".join(lines[start:]).rstrip()


def _slice_content(content: str, offset: int, max_chars: int) -> tuple[str, bool]:
    """Take a slice of content, preferring to end on a line boundary.

    Args:
        content: Text to slice.
        offset: Starting character offset.
        max_chars: Maximum characters to return.

    Returns:
        Tuple of (slice, more_remaining).
    """
    if offset >= len(content):
        return "", False

    chunk = content[offset : offset + max_chars]
    more = offset + len(chunk) < len(content)

    if more:
        # Avoid cutting mid-line; keep the whole chunk if there is no newline
        # to fall back to.
        newline = chunk.rfind("\n")
        if newline > 0:
            chunk = chunk[:newline]

    return chunk, offset + len(chunk) < len(content)


def get_doc(
    topic: str,
    section: str | None = None,
    offset: int = 0,
    max_chars: int = DEFAULT_DOC_MAX_CHARS,
) -> DocContent | None:
    """Get a slice of a documentation page.

    Args:
        topic: Topic name to retrieve.
        section: Optional level-2 heading to return instead of the whole page.
        offset: Character offset to start reading from.
        max_chars: Maximum characters to return.

    Returns:
        DocContent for the requested slice, or None if docs unavailable.

    Raises:
        DocTopicNotFoundError: If the topic does not exist.
        DocSectionNotFoundError: If the requested section does not exist.
    """
    validated_topic = validate_doc_topic(topic)
    # Explicit None check: with a truthiness test an empty string silently
    # meant "whole page", while a whitespace-only one was rejected.
    validated_section = validate_doc_section(section) if section is not None else None
    capped_chars = max(1, min(max_chars, MAX_DOC_MAX_CHARS))
    start = max(0, offset)

    index = _load_docs_index()
    if index is None:
        return None

    entry = index.get(validated_topic)
    if entry is None:
        available = sorted(index.keys())
        suggestions = [t for t in available if validated_topic in t or t in validated_topic][:5]
        msg = f"Documentation topic '{validated_topic}' not found."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        else:
            msg += " Use freqtrade_list_docs to see available topics."
        raise DocTopicNotFoundError(msg)

    title, content, size = entry
    sections = _list_sections(content)

    scope = content
    if validated_section is not None:
        extracted = _extract_section(content, validated_section)
        if extracted is None:
            msg = (
                f"Section '{validated_section}' not found in '{validated_topic}'. "
                f"Available sections: {', '.join(sections) if sections else '(none)'}."
            )
            raise DocSectionNotFoundError(msg)
        scope = extracted

    chunk, more = _slice_content(scope, start, capped_chars)

    return DocContent(
        topic=validated_topic,
        title=title,
        content=chunk,
        size_bytes=size,
        section=validated_section,
        sections=sections,
        offset=start,
        returned_chars=len(chunk),
        total_chars=len(scope),
        truncated=more,
        next_offset=start + len(chunk) if more else None,
    )
