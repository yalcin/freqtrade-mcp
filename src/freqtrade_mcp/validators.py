"""Input validation and sanitization for MCP tool parameters.

All LLM-generated inputs must pass through these validators before use.
Uses a whitelist approach: only explicitly allowed patterns are accepted.
"""

import re

from freqtrade_mcp.constants import (
    ALLOWED_TOP_LEVEL_MODULE,
    DOC_TOPIC_PATTERN,
    FILTER_PATTERN,
    IDENTIFIER_PATTERN,
    MAX_INPUT_LENGTH,
    MODULE_PATH_PATTERN,
    SAFE_REGEX_PATTERN,
)
from freqtrade_mcp.exceptions import ValidationError


def validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate that a string is a valid Python identifier.

    Args:
        name: The identifier string to validate.
        label: Human-readable label for error messages.

    Returns:
        The validated identifier string.

    Raises:
        ValidationError: If the string is not a valid Python identifier.
    """
    if not name or len(name) > MAX_INPUT_LENGTH:
        msg = f"Invalid {label}: must be 1-{MAX_INPUT_LENGTH} characters, got {len(name)}."
        raise ValidationError(msg)

    if not IDENTIFIER_PATTERN.match(name):
        msg = (
            f"Invalid {label}: '{name}' is not a valid Python identifier. "
            "Only letters, digits, and underscores are allowed."
        )
        raise ValidationError(msg)

    return name


def validate_module_path(path: str) -> str:
    """Validate that a string is a valid freqtrade module path.

    Args:
        path: The module path to validate (e.g., "freqtrade.strategy.interface").

    Returns:
        The validated module path string.

    Raises:
        ValidationError: If the path is invalid or not under the freqtrade namespace.
    """
    if not path or len(path) > MAX_INPUT_LENGTH:
        msg = f"Invalid module path: must be 1-{MAX_INPUT_LENGTH} characters, got {len(path)}."
        raise ValidationError(msg)

    if not path.startswith(f"{ALLOWED_TOP_LEVEL_MODULE}."):
        msg = (
            f"Invalid module path: '{path}' must start with '{ALLOWED_TOP_LEVEL_MODULE}.'. "
            "Only freqtrade modules can be inspected."
        )
        raise ValidationError(msg)

    if not MODULE_PATH_PATTERN.match(path):
        msg = (
            f"Invalid module path: '{path}' contains invalid characters. "
            "Only valid Python module paths under freqtrade.* are allowed."
        )
        raise ValidationError(msg)

    return path


def validate_class_path(path: str) -> tuple[str, str]:
    """Validate and split a fully-qualified class path.

    Args:
        path: Fully-qualified class path (e.g., "freqtrade.strategy.interface.IStrategy").

    Returns:
        Tuple of (module_path, class_name).

    Raises:
        ValidationError: If the path is invalid.
    """
    if not path or len(path) > MAX_INPUT_LENGTH:
        msg = f"Invalid class path: must be 1-{MAX_INPUT_LENGTH} characters, got {len(path)}."
        raise ValidationError(msg)

    parts = path.rsplit(".", maxsplit=1)
    if len(parts) != 2:
        msg = (
            f"Invalid class path: '{path}' must be a dotted path "
            "like 'freqtrade.strategy.interface.IStrategy'."
        )
        raise ValidationError(msg)

    module_path, class_name = parts
    validate_module_path(module_path)
    validate_identifier(class_name, label="class name")

    return module_path, class_name


def validate_search_pattern(pattern: str) -> re.Pattern[str]:
    """Validate and compile a search regex pattern.

    Restricts the pattern to a whitelisted character set and caps its length,
    limiting (but not eliminating) ReDoS and injection risk.

    Args:
        pattern: Regex pattern string to validate.

    Returns:
        Compiled regex pattern.

    Raises:
        ValidationError: If the pattern is invalid or contains unsafe characters.
    """
    if not pattern or len(pattern) > MAX_INPUT_LENGTH:
        msg = (
            f"Invalid search pattern: must be 1-{MAX_INPUT_LENGTH} characters, got {len(pattern)}."
        )
        raise ValidationError(msg)

    if not SAFE_REGEX_PATTERN.match(pattern):
        msg = (
            f"Invalid search pattern: '{pattern}' contains unsafe characters. "
            "Only alphanumeric characters, underscores, and basic regex operators are allowed."
        )
        raise ValidationError(msg)

    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        msg = f"Invalid regex pattern: '{pattern}' — {e}"
        raise ValidationError(msg) from e


def validate_filter_string(value: str, label: str = "filter") -> str:
    """Validate a simple filter string (no regex; letters, digits, `_`, `-`, spaces).

    Args:
        value: The filter string to validate.
        label: Human-readable label for error messages.

    Returns:
        The validated filter string, stripped and lowercased.

    Raises:
        ValidationError: If the string is empty after stripping or contains
            invalid characters.
    """
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_INPUT_LENGTH:
        msg = f"Invalid {label}: must be 1-{MAX_INPUT_LENGTH} non-empty characters."
        raise ValidationError(msg)

    if not FILTER_PATTERN.match(normalized):
        msg = (
            f"Invalid {label}: '{value}' contains invalid characters. "
            "Only letters, digits, underscores, hyphens, and spaces are allowed."
        )
        raise ValidationError(msg)

    return normalized.lower()


def validate_doc_topic(topic: str) -> str:
    """Validate a documentation topic name.

    Ensures the topic contains only safe characters (alphanumeric, hyphens,
    underscores) with optional single-level subdirectory separator.
    Prevents path traversal attacks.

    Args:
        topic: The topic name to validate (e.g., "strategy-callbacks",
            "commands/backtesting").

    Returns:
        The validated topic string.

    Raises:
        ValidationError: If the topic contains invalid characters or
            path traversal sequences.
    """
    if not topic or len(topic) > MAX_INPUT_LENGTH:
        msg = f"Invalid doc topic: must be 1-{MAX_INPUT_LENGTH} characters, got {len(topic)}."
        raise ValidationError(msg)

    if not DOC_TOPIC_PATTERN.match(topic):
        msg = (
            f"Invalid doc topic: '{topic}' contains invalid characters. "
            "Only alphanumeric characters, hyphens, underscores, and "
            "a single '/' for subdirectories are allowed."
        )
        raise ValidationError(msg)

    return topic


def validate_doc_section(section: str) -> str:
    """Validate a documentation section heading.

    Headings are free-form markdown text, so this only bounds the length and
    rejects empty input. The value is matched against the headings actually
    present in the page, never used to build a path or a pattern.

    Args:
        section: Section heading to validate.

    Returns:
        The stripped section heading.

    Raises:
        ValidationError: If the section is empty or too long.
    """
    normalized = section.strip()
    if not normalized or len(normalized) > MAX_INPUT_LENGTH:
        msg = f"Invalid doc section: must be 1-{MAX_INPUT_LENGTH} non-empty characters."
        raise ValidationError(msg)

    return normalized


def validate_doc_search_query(query: str) -> str:
    """Validate a documentation search query.

    Args:
        query: Search text to validate.

    Returns:
        The validated and stripped search query string.

    Raises:
        ValidationError: If the query is empty or too long.
    """
    if not query or not query.strip() or len(query) > MAX_INPUT_LENGTH:
        msg = f"Invalid search query: must be 1-{MAX_INPUT_LENGTH} non-empty characters."
        raise ValidationError(msg)

    return query.strip()
