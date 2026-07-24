"""Pydantic models for MCP tool inputs and outputs."""

from pydantic import BaseModel, Field

from freqtrade_mcp.constants import (
    DEFAULT_DOC_MAX_CHARS,
    DEFAULT_SYMBOL_SEARCH_RESULTS,
    MAX_DOC_MAX_CHARS,
    MAX_SYMBOL_SEARCH_RESULTS,
)

# --- Input Models ---


class ListStrategyMethodsInput(BaseModel):
    """Input for freqtrade_list_strategy_methods tool."""

    filter: str | None = Field(
        default=None,
        description=(
            "Optional filter to narrow results. "
            "Examples: 'indicator', 'entry', 'exit', 'callback', 'custom'."
        ),
        max_length=256,
    )


class GetMethodSignatureInput(BaseModel):
    """Input for freqtrade_get_method_signature tool."""

    method_name: str = Field(
        description="Name of the IStrategy method to inspect.",
        max_length=256,
    )


class GetClassInfoInput(BaseModel):
    """Input for freqtrade_get_class_info tool."""

    class_path: str = Field(
        description=(
            "Fully-qualified class path. Example: 'freqtrade.strategy.interface.IStrategy'."
        ),
        max_length=256,
    )


class ListEnumsInput(BaseModel):
    """Input for freqtrade_list_enums tool."""

    filter: str | None = Field(
        default=None,
        description="Optional filter pattern to narrow enum results.",
        max_length=256,
    )


class GetEnumValuesInput(BaseModel):
    """Input for freqtrade_get_enum_values tool."""

    enum_path: str = Field(
        description=(
            "Fully-qualified enum path. Example: 'freqtrade.enums.signaltype.SignalDirection'."
        ),
        max_length=256,
    )


class SearchCodebaseInput(BaseModel):
    """Input for freqtrade_search_codebase tool."""

    query: str = Field(
        description=(
            "Search pattern for symbol names (classes, functions, constants). "
            "Supports basic regex (alphanumeric, underscores, wildcards)."
        ),
        max_length=256,
    )
    max_results: int = Field(
        default=DEFAULT_SYMBOL_SEARCH_RESULTS,
        description="Maximum number of symbols to return (1-500).",
        ge=1,
        le=MAX_SYMBOL_SEARCH_RESULTS,
    )


class GetCallbackInfoInput(BaseModel):
    """Input for freqtrade_get_callback_info tool."""

    callback_name: str = Field(
        description=(
            "Name of the strategy callback method. "
            "Examples: 'bot_start', 'custom_stake_amount', 'custom_stoploss'."
        ),
        max_length=256,
    )


class GetConfigSchemaInput(BaseModel):
    """Input for freqtrade_get_config_schema tool."""

    section: str | None = Field(
        default=None,
        description=(
            "Optional config section filter. "
            "Examples: 'exchange', 'pairlist', 'stoploss', 'order_types'."
        ),
        max_length=256,
    )


class GetDataframeColumnsInput(BaseModel):
    """Input for freqtrade_get_dataframe_columns tool."""

    context: str | None = Field(
        default=None,
        description=(
            "Optional context filter for columns. "
            "Options: 'ohlcv', 'entry', 'exit', 'indicators'. "
            "If omitted, returns all known columns."
        ),
        max_length=256,
    )


class ListDocsInput(BaseModel):
    """Input for freqtrade_list_docs tool."""

    filter: str | None = Field(
        default=None,
        description=(
            "Optional keyword filter for doc topics. "
            "Examples: 'strategy', 'freqai', 'backtesting'."
        ),
        max_length=256,
    )


class SearchDocsInput(BaseModel):
    """Input for freqtrade_search_docs tool."""

    query: str = Field(
        description=(
            "Search query text. Searches across all documentation content. "
            "Multiple words use AND logic."
        ),
        max_length=256,
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of matching snippets to return (1-50).",
        ge=1,
        le=50,
    )


class GetDocInput(BaseModel):
    """Input for freqtrade_get_doc tool."""

    topic: str = Field(
        description=(
            "Documentation topic name. Examples: 'strategy-callbacks', "
            "'configuration', 'commands/backtesting'. "
            "Use freqtrade_list_docs to discover available topics."
        ),
        max_length=256,
    )
    section: str | None = Field(
        default=None,
        description=(
            "Optional section heading to return instead of the whole page. "
            "Matched case-insensitively against the page's '##' headings, "
            "which are always listed in the 'sections' field of the response."
        ),
        max_length=256,
    )
    offset: int = Field(
        default=0,
        description="Character offset to resume reading from (see next_offset).",
        ge=0,
    )
    max_chars: int = Field(
        default=DEFAULT_DOC_MAX_CHARS,
        description="Maximum number of characters to return (1-100000).",
        ge=1,
        le=MAX_DOC_MAX_CHARS,
    )


# --- Output Models ---


class MethodSummary(BaseModel):
    """Summary of a single method."""

    name: str = Field(description="Method name.")
    brief: str = Field(description="Brief one-line description.")
    is_callback: bool = Field(description="Whether this is a strategy callback method.")


class ParameterInfo(BaseModel):
    """Detailed parameter information."""

    name: str = Field(description="Parameter name.")
    annotation: str = Field(description="Type annotation string.")
    default: str | None = Field(description="Default value if any.")
    kind: str = Field(description="Parameter kind (POSITIONAL_OR_KEYWORD, etc.).")


class MethodSignature(BaseModel):
    """Full method signature details."""

    name: str = Field(description="Method name.")
    parameters: list[ParameterInfo] = Field(description="Method parameters.")
    return_type: str = Field(description="Return type annotation.")
    docstring: str | None = Field(description="Full docstring.")
    source_file: str | None = Field(description="Source file path (relative).")


class ClassInfo(BaseModel):
    """Class introspection result."""

    name: str = Field(description="Class name.")
    module: str = Field(description="Module path.")
    docstring: str | None = Field(description="Class docstring.")
    method_resolution_order: list[str] = Field(
        description="Method resolution order (class names)."
    )
    public_methods: list[str] = Field(description="List of public method names.")
    class_attributes: dict[str, str] = Field(
        description="Class-level attributes with their type/value descriptions."
    )


class EnumSummary(BaseModel):
    """Summary of an enum."""

    name: str = Field(description="Enum class name.")
    module: str = Field(description="Module path.")
    docstring: str | None = Field(description="Enum docstring.")
    member_count: int = Field(description="Number of enum members.")


class EnumMember(BaseModel):
    """A single enum member."""

    name: str = Field(description="Member name.")
    value: str = Field(description="Member value as string.")


class EnumDetail(BaseModel):
    """Detailed enum information."""

    name: str = Field(description="Enum class name.")
    module: str = Field(description="Module path.")
    docstring: str | None = Field(description="Enum docstring.")
    members: list[EnumMember] = Field(description="All enum members.")


class SymbolMatch(BaseModel):
    """A symbol found by codebase search."""

    name: str = Field(description="Symbol name.")
    module: str = Field(description="Module containing the symbol.")
    kind: str = Field(description="Symbol kind: 'class', 'function', 'constant', 'enum'.")


class SymbolSearchResult(BaseModel):
    """Result of a codebase symbol search.

    Completeness is reported explicitly: a caller must be able to tell a
    genuinely empty result from a truncated one, and a full scan from one where
    part of the freqtrade tree could not be imported.
    """

    matches: list[SymbolMatch] = Field(description="Matching symbols (capped at max_results).")
    returned: int = Field(description="Number of symbols in this response.")
    total_matches: int = Field(description="Total symbols matched before truncation.")
    truncated: bool = Field(
        description="True if more symbols matched than were returned; refine the query."
    )
    skipped_modules: list[str] = Field(
        description=(
            "Modules whose source could not be read or parsed, and which were "
            "therefore not searched. Results are incomplete when this is non-empty."
        )
    )
    skipped_module_count: int = Field(
        description="Total number of skipped modules (skipped_modules may be truncated)."
    )


class CallbackInfo(BaseModel):
    """Detailed callback method information."""

    name: str = Field(description="Callback method name.")
    signature: str = Field(description="Full method signature string.")
    parameters: list[ParameterInfo] = Field(description="Method parameters.")
    return_type: str = Field(description="Return type annotation.")
    docstring: str | None = Field(description="Full docstring.")


class ConfigKey(BaseModel):
    """A configuration key entry."""

    key: str = Field(description="Configuration key name.")
    description: str = Field(description="Description of the config key.")


class DataframeColumn(BaseModel):
    """A DataFrame column entry."""

    name: str = Field(description="Column name.")
    description: str = Field(description="Column description including type.")
    context: str = Field(description="Context where this column is available.")


class VersionInfo(BaseModel):
    """Version and environment information."""

    mcp_server_version: str = Field(description="freqtrade-mcp server version.")
    freqtrade_version: str = Field(description="Installed freqtrade version.")
    python_version: str = Field(description="Python version.")


class DocTopic(BaseModel):
    """Summary of a documentation topic."""

    topic: str = Field(description="Topic identifier (e.g., 'strategy-callbacks').")
    title: str = Field(description="Human-readable title from the document.")
    path: str = Field(description="Relative file path within the docs directory.")
    size_bytes: int = Field(description="File size in bytes.")


class DocSearchResult(BaseModel):
    """A search result snippet from the documentation."""

    topic: str = Field(description="Topic where the match was found.")
    title: str = Field(description="Document title.")
    line_number: int = Field(description="Line number of the first match in the snippet.")
    snippet: str = Field(description="Context snippet around the match.")


class DocContent(BaseModel):
    """A page of documentation content.

    Pages are returned in slices: freqtrade's largest page is ~70 KB, which is
    ~17k tokens in one response. Read the whole page by following
    ``next_offset``, or jump straight to a heading with ``section``.
    """

    topic: str = Field(description="Topic identifier.")
    title: str = Field(description="Document title.")
    content: str = Field(description="Markdown content for the requested slice.")
    size_bytes: int = Field(description="Size of the whole page in bytes.")
    section: str | None = Field(
        default=None, description="Section heading returned, if one was requested."
    )
    sections: list[str] = Field(
        default_factory=list,
        description="All '##' headings in the page; usable as the 'section' argument.",
    )
    offset: int = Field(default=0, description="Character offset this slice starts at.")
    returned_chars: int = Field(default=0, description="Number of characters in this slice.")
    total_chars: int = Field(
        default=0, description="Total characters available in the requested scope."
    )
    truncated: bool = Field(default=False, description="True if content remains after this slice.")
    next_offset: int | None = Field(
        default=None, description="Offset to pass back to read the next slice, if any."
    )
