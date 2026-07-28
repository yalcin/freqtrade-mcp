"""FastMCP server entry point for freqtrade-mcp.

This MCP server is strictly read-only. It inspects the installed Freqtrade
library using Python's ``inspect`` module. It does not execute trades,
connect to exchanges, modify configuration, or perform any operation with
side effects. No warranty is provided — see LICENSE.
"""

import json
import logging
import os
import sys
from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

import anyio.to_thread
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

import freqtrade_mcp
from freqtrade_mcp._version_check import check_freqtrade_importable, check_freqtrade_version
from freqtrade_mcp.constants import (
    DEFAULT_DOC_MAX_CHARS,
    DEFAULT_LOG_LEVEL,
    DEFAULT_SYMBOL_SEARCH_RESULTS,
    DOCS_UNAVAILABLE_MSG,
    ENV_DOCS_PATH,
    ENV_LOG_LEVEL,
    LOG_LEVELS,
    MAX_DOC_MAX_CHARS,
    MAX_SYMBOL_SEARCH_RESULTS,
    SERVER_DESCRIPTION,
    SERVER_NAME,
)
from freqtrade_mcp.docs import get_doc, list_docs, search_docs
from freqtrade_mcp.exceptions import VersionError
from freqtrade_mcp.introspection import (
    get_callback_info,
    get_class_info,
    get_config_schema,
    get_dataframe_columns,
    get_enum_values,
    get_method_signature,
    list_enums,
    list_strategy_methods,
    search_codebase,
)
from freqtrade_mcp.models import (
    GetCallbackInfoInput,
    GetClassInfoInput,
    GetConfigSchemaInput,
    GetDataframeColumnsInput,
    GetDocInput,
    GetEnumValuesInput,
    GetMethodSignatureInput,
    ListDocsInput,
    ListEnumsInput,
    ListStrategyMethodsInput,
    SearchCodebaseInput,
    SearchDocsInput,
)

logger = logging.getLogger(__name__)

# Tool annotations: all tools are read-only, non-destructive, idempotent, closed-world
_TOOL_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

# Create the FastMCP server
mcp = FastMCP(SERVER_NAME, instructions=SERVER_DESCRIPTION)


async def _run_sync[T](func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking introspection helper in a worker thread.

    FastMCP invokes synchronous tool functions inline on the event loop, so any
    blocking work stalls the entire server: no concurrent tool calls, no
    keepalive, no cancellation. Importing the freqtrade package tree alone
    takes seconds on the first symbol search, so every tool body is offloaded.

    Args:
        func: Blocking callable to execute.
        *args: Positional arguments for ``func``.
        **kwargs: Keyword arguments for ``func``.

    Returns:
        Whatever ``func`` returns.
    """
    return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))


# --- Tool Definitions ---


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_list_strategy_methods(
    filter: Annotated[  # noqa: A002
        str | None,
        Field(
            description=(
                "Optional filter to narrow results. "
                "Examples: 'indicator', 'entry', 'exit', 'callback', 'custom'."
            ),
            max_length=256,
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """List all overridable methods from IStrategy.

    Returns method names with brief descriptions. Use the optional filter
    parameter to narrow results by keyword (e.g., "entry", "exit",
    "indicator", "callback", "custom").

    Args:
        filter: Optional keyword to filter methods.

    Returns:
        List of method summaries with name, brief description, and callback flag.
    """
    input_model = ListStrategyMethodsInput(filter=filter)
    methods = await _run_sync(list_strategy_methods, filter_str=input_model.filter)
    return [m.model_dump() for m in methods]


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_method_signature(
    method_name: Annotated[
        str,
        Field(description="Name of the IStrategy method to inspect.", max_length=256),
    ],
) -> dict[str, Any]:
    """Get full signature of a specific IStrategy method.

    Returns the complete method signature including all parameters with their
    types, default values, return type, and the full docstring.

    Args:
        method_name: Name of the IStrategy method to inspect.

    Returns:
        Method signature details including parameters, return type, and docstring.
    """
    input_model = GetMethodSignatureInput(method_name=method_name)
    result = await _run_sync(get_method_signature, input_model.method_name)
    return result.model_dump()


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_class_info(
    class_path: Annotated[
        str,
        Field(
            description=(
                "Fully-qualified class path. Example: 'freqtrade.strategy.interface.IStrategy'."
            ),
            max_length=256,
        ),
    ],
) -> dict[str, Any]:
    """Inspect any freqtrade class.

    Returns class docstring, method resolution order (MRO), public methods,
    and class-level attributes for a given fully-qualified class path.

    Args:
        class_path: Fully-qualified class path
            (e.g., "freqtrade.strategy.interface.IStrategy").

    Returns:
        Class introspection result with docstring, MRO, methods, and attributes.
    """
    input_model = GetClassInfoInput(class_path=class_path)
    result = await _run_sync(get_class_info, input_model.class_path)
    return result.model_dump()


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_list_enums(
    filter: Annotated[  # noqa: A002
        str | None,
        Field(description="Optional filter pattern to narrow enum results.", max_length=256),
    ] = None,
) -> list[dict[str, Any]]:
    """List all trading-related enums from freqtrade.

    Returns enum names, their module paths, docstrings, and member counts.
    Use the optional filter to narrow results.

    Args:
        filter: Optional keyword filter for enum names or descriptions.

    Returns:
        List of enum summaries.
    """
    input_model = ListEnumsInput(filter=filter)
    enums = await _run_sync(list_enums, filter_str=input_model.filter)
    return [e.model_dump() for e in enums]


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_enum_values(
    enum_path: Annotated[
        str,
        Field(
            description=(
                "Fully-qualified enum path. Example: 'freqtrade.enums.signaltype.SignalDirection'."
            ),
            max_length=256,
        ),
    ],
) -> dict[str, Any]:
    """Get all values of a specific freqtrade enum.

    Returns every member of the enum with its name and value.

    Args:
        enum_path: Fully-qualified enum path
            (e.g., "freqtrade.enums.signaltype.SignalDirection").

    Returns:
        Enum details including all member names and values.
    """
    input_model = GetEnumValuesInput(enum_path=enum_path)
    result = await _run_sync(get_enum_values, input_model.enum_path)
    return result.model_dump()


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_search_codebase(
    query: Annotated[
        str,
        Field(
            description=(
                "Search pattern for symbol names (classes, functions, constants). "
                "Supports safe glob-style wildcards: '*' for any sequence, '?' for "
                "one character, and optional leading '^' / trailing '$' anchors."
            ),
            max_length=256,
        ),
    ],
    max_results: Annotated[
        int,
        Field(
            description="Maximum number of symbols to return (1-500).",
            ge=1,
            le=MAX_SYMBOL_SEARCH_RESULTS,
        ),
    ] = DEFAULT_SYMBOL_SEARCH_RESULTS,
) -> dict[str, Any]:
    """Search for symbols in the freqtrade codebase by name pattern.

    Searches for classes, functions, constants, and enums matching the given
    pattern. Supports safe glob-style wildcards: ``*`` for any sequence, ``?``
    for one character, and optional leading ``^`` / trailing ``$`` anchors.
    The legacy ``.*`` spelling is accepted as an alias for ``*``.

    The response reports completeness explicitly. Check ``truncated`` before
    concluding that a symbol does not exist: a broad pattern such as ".*"
    matches thousands of symbols and only the first ``max_results`` are
    returned. Check ``skipped_modules`` too — a non-empty list means part of
    the freqtrade tree could not be parsed and was never searched.

    Args:
        query: Safe glob-style search pattern for symbol names.
        max_results: Maximum number of symbols to return (1-500, default 50).

    Returns:
        Search result with matches, total_matches, truncated, and skipped_modules.
    """
    input_model = SearchCodebaseInput(query=query, max_results=max_results)
    result = await _run_sync(
        search_codebase,
        input_model.query,
        max_results=input_model.max_results,
    )
    return result.model_dump()


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_callback_info(
    callback_name: Annotated[
        str,
        Field(
            description=(
                "Name of the strategy callback method. "
                "Examples: 'bot_start', 'custom_stake_amount', 'custom_stoploss'."
            ),
            max_length=256,
        ),
    ],
) -> dict[str, Any]:
    """Get detailed info about a strategy callback method.

    Returns the full signature, parameters with types, return type,
    and docstring for a strategy callback like bot_start,
    custom_stake_amount, custom_stoploss, etc.

    Args:
        callback_name: Name of the strategy callback method.

    Returns:
        Detailed callback information including signature and docstring.
    """
    input_model = GetCallbackInfoInput(callback_name=callback_name)
    result = await _run_sync(get_callback_info, input_model.callback_name)
    return result.model_dump()


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_config_schema(
    section: Annotated[
        str | None,
        Field(
            description=(
                "Optional config section filter. "
                "Examples: 'exchange', 'pairlists', 'stoploss', 'order_types'."
            ),
            max_length=256,
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """Return live freqtrade configuration keys and their descriptions.

    Reads the JSON schema from the installed Freqtrade version. Use the optional
    section parameter to filter by a key or description.

    Args:
        section: Optional section filter (e.g., "exchange", "pairlists", "stoploss").

    Returns:
        List of config key entries with descriptions.
    """
    input_model = GetConfigSchemaInput(section=section)
    keys = await _run_sync(get_config_schema, section=input_model.section)
    return [k.model_dump() for k in keys]


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_dataframe_columns(
    context: Annotated[
        str | None,
        Field(
            description=(
                "Optional context filter for columns. "
                "Options: 'ohlcv', 'entry', 'exit', 'indicators'. "
                "If omitted, returns all known columns."
            ),
            max_length=256,
        ),
    ] = None,
) -> list[dict[str, Any]]:
    """List common DataFrame columns available in strategy methods.

    Returns column names, types, and descriptions for columns available in
    populate_indicators, populate_entry_trend, populate_exit_trend, etc.
    Columns in the "indicators" context are conventional names only — they
    exist in the DataFrame only if the strategy computes them.

    Args:
        context: Optional context filter: "ohlcv", "entry", "exit", or "indicators".
            If omitted, returns all known columns.

    Returns:
        List of DataFrame column entries with descriptions and contexts.
    """
    input_model = GetDataframeColumnsInput(context=context)
    columns = await _run_sync(get_dataframe_columns, context=input_model.context)
    return [c.model_dump() for c in columns]


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_version_info() -> dict[str, str]:
    """Return installed freqtrade version and MCP server version.

    Returns version information including the freqtrade-mcp server version,
    installed freqtrade version, and Python version.

    Returns:
        Version information dictionary.
    """
    ft_version = await _run_sync(check_freqtrade_version)
    return {
        "mcp_server_version": freqtrade_mcp.__version__,
        "freqtrade_version": ft_version,
        "python_version": sys.version,
    }


# --- Documentation Tools ---


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_list_docs(
    filter: Annotated[  # noqa: A002
        str | None,
        Field(
            description=(
                "Optional keyword filter for doc topics. "
                "Examples: 'strategy', 'freqai', 'backtesting'."
            ),
            max_length=256,
        ),
    ] = None,
) -> list[dict[str, Any]] | dict[str, str]:
    """List available freqtrade documentation topics.

    Returns a list of documentation pages with their topic identifiers
    and titles. Use the optional filter to narrow results by keyword.

    Args:
        filter: Optional keyword to filter topics (e.g., "strategy", "freqai").

    Returns:
        List of doc topic summaries, or an error message if docs not available.
    """
    input_model = ListDocsInput(filter=filter)
    result = await _run_sync(list_docs, filter_str=input_model.filter)
    if result is None:
        return {"error": DOCS_UNAVAILABLE_MSG}
    return [t.model_dump() for t in result]


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_search_docs(
    query: Annotated[
        str,
        Field(
            description=(
                "Search query text. Searches across all documentation content. "
                "Multiple words use AND logic."
            ),
            max_length=256,
        ),
    ],
    max_results: Annotated[
        int,
        Field(description="Maximum number of matching snippets to return (1-50).", ge=1, le=50),
    ] = 10,
) -> list[dict[str, Any]] | dict[str, str]:
    """Search across all freqtrade documentation.

    Performs full-text search across all documentation pages and returns
    matching snippets with surrounding context. Multiple words use AND logic.

    Args:
        query: Search text (e.g., "custom stoploss", "backtesting timerange").
        max_results: Maximum number of results to return (1-50, default 10).

    Returns:
        List of search results with snippets, or error if docs not available.
    """
    input_model = SearchDocsInput(query=query, max_results=max_results)
    result = await _run_sync(
        search_docs, query=input_model.query, max_results=input_model.max_results
    )
    if result is None:
        return {"error": DOCS_UNAVAILABLE_MSG}
    return [r.model_dump() for r in result]


@mcp.tool(annotations=_TOOL_ANNOTATIONS)
async def freqtrade_get_doc(
    topic: Annotated[
        str,
        Field(
            description=(
                "Documentation topic name. Examples: 'strategy-callbacks', 'configuration', "
                "'commands/backtesting'. Use freqtrade_list_docs to discover available topics."
            ),
            max_length=256,
        ),
    ],
    section: Annotated[
        str | None,
        Field(
            description=(
                "Optional section heading to return instead of the whole page. "
                "Matched case-insensitively against the page's '##' headings, which "
                "are always listed in the 'sections' field of the response."
            ),
            max_length=256,
        ),
    ] = None,
    offset: Annotated[
        int,
        Field(description="Character offset to resume reading from (see next_offset).", ge=0),
    ] = 0,
    max_chars: Annotated[
        int,
        Field(
            description="Maximum number of characters to return (1-100000).",
            ge=1,
            le=MAX_DOC_MAX_CHARS,
        ),
    ] = DEFAULT_DOC_MAX_CHARS,
) -> dict[str, Any] | dict[str, str]:
    """Read a freqtrade documentation page, or one section of it.

    Pages are returned in slices — freqtrade's largest page is ~70 KB, roughly
    17k tokens in a single response. The response always lists the page's '##'
    headings in ``sections``: pass one back as ``section`` to read just that
    part. To read a long page in full, follow ``next_offset`` until
    ``truncated`` is false.

    Args:
        topic: Topic name (e.g., "strategy-callbacks", "configuration",
            "commands/backtesting").
        section: Optional section heading to return instead of the whole page.
        offset: Character offset to resume reading from.
        max_chars: Maximum characters to return (1-100000, default 20000).

    Returns:
        Document slice with sections, pagination state, and metadata, or an
        error if documentation is not available.
    """
    input_model = GetDocInput(topic=topic, section=section, offset=offset, max_chars=max_chars)
    result = await _run_sync(
        get_doc,
        topic=input_model.topic,
        section=input_model.section,
        offset=input_model.offset,
        max_chars=input_model.max_chars,
    )
    if result is None:
        return {"error": DOCS_UNAVAILABLE_MSG}
    return result.model_dump()


class _JsonFormatter(logging.Formatter):
    """Serialize each log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def _configure_logging() -> None:
    """Configure logging to stderr with JSON structured output.

    Safe to call more than once: existing handlers are replaced rather than
    stacked. An unknown log level falls back to WARNING with a warning instead
    of raising, and propagation to the root logger is disabled so that a root
    handler writing to stdout can never corrupt the JSON-RPC stream.
    """
    requested = os.environ.get(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL).strip().upper()
    level = LOG_LEVELS.get(requested)

    pkg_logger = logging.getLogger("freqtrade_mcp")
    pkg_logger.propagate = False
    for existing in list(pkg_logger.handlers):
        pkg_logger.removeHandler(existing)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    pkg_logger.addHandler(handler)
    pkg_logger.setLevel(level if level is not None else LOG_LEVELS[DEFAULT_LOG_LEVEL])

    if level is None:
        pkg_logger.warning(
            "Unknown %s=%r; falling back to %s. Valid levels: %s.",
            ENV_LOG_LEVEL,
            requested,
            DEFAULT_LOG_LEVEL,
            ", ".join(sorted(LOG_LEVELS)),
        )


def _validate_freqtrade_installation() -> str:
    """Check the freqtrade installation and report what will not work.

    A missing or too-old freqtrade is fatal. Being unable to *import* it is
    not: freqtrade declares scipy only under its ``hyperopt`` extra while
    ``freqtrade.data.metrics`` imports it unconditionally, so a stock
    ``pip install freqtrade`` cannot import the strategy interface. Symbol
    search reads the source tree statically and the documentation tools do not
    touch freqtrade at all, so most of the server still works — refusing to
    start would disable those for no reason.

    Returns:
        The installed freqtrade version.

    Raises:
        VersionError: If freqtrade is missing or below the minimum version.
    """
    ft_version = check_freqtrade_version()

    try:
        check_freqtrade_importable()
    except VersionError as e:
        logger.warning(
            "%s Tools that introspect live objects (strategy methods, class "
            "info, callbacks, enums) will fail until this is fixed; symbol "
            "search and the documentation tools are unaffected.",
            e,
        )

    return ft_version


def main() -> None:
    """Run the freqtrade-mcp server.

    Validates the freqtrade installation, configures logging, and starts
    the MCP server with stdio transport.
    """
    _configure_logging()

    try:
        ft_version = _validate_freqtrade_installation()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Check if docs are available (non-fatal)
    from freqtrade_mcp.docs import _discover_docs_path

    docs_path = _discover_docs_path()
    if docs_path:
        logger.info("Freqtrade docs available at: %s", docs_path)
    else:
        logger.warning(
            "Freqtrade docs not found. Doc tools will return guidance. Set %s to enable.",
            ENV_DOCS_PATH,
        )

    logger.info(
        "Starting %s v%s (freqtrade %s)",
        SERVER_NAME,
        freqtrade_mcp.__version__,
        ft_version,
    )

    mcp.run()


if __name__ == "__main__":
    main()
