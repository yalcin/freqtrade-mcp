"""Core introspection engine for the freqtrade codebase.

Uses Python's ``inspect`` module to extract metadata from
freqtrade classes, methods, enums, and configuration. Never uses
``eval()`` or ``exec()``.
"""

import enum
import importlib
import inspect
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

from freqtrade_mcp.cache import ttl_cache
from freqtrade_mcp.constants import (
    CONFIG_SECTIONS,
    DATAFRAME_CONTEXTS,
    DEFAULT_SYMBOL_SEARCH_RESULTS,
    ISTRATEGY_CLASS_PATH,
    MAX_REPORTED_SKIPPED_MODULES,
    MAX_SYMBOL_SEARCH_RESULTS,
    STRATEGY_CALLBACKS,
)
from freqtrade_mcp.exceptions import (
    ClassNotFoundError,
    IntrospectionError,
    MethodNotFoundError,
    ModuleImportError,
)
from freqtrade_mcp.models import (
    CallbackInfo,
    ClassInfo,
    ConfigKey,
    DataframeColumn,
    EnumDetail,
    EnumMember,
    EnumSummary,
    MethodSignature,
    MethodSummary,
    ParameterInfo,
    SymbolSearchResult,
)
from freqtrade_mcp.symbols import _freqtrade_package_root, build_symbol_index
from freqtrade_mcp.validators import (
    validate_class_path,
    validate_filter_string,
    validate_identifier,
    validate_search_pattern,
)

logger = logging.getLogger(__name__)


def _import_module(module_path: str) -> ModuleType:
    """Safely import a freqtrade module.

    Args:
        module_path: Validated module path.

    Returns:
        The imported module.

    Raises:
        ModuleImportError: If the module cannot be imported.
    """
    try:
        return importlib.import_module(module_path)
    except (Exception, SystemExit) as e:
        # Deliberately broad: importing a module runs its top-level code, which
        # can raise anything. SystemExit is included on purpose and is not
        # theoretical — freqtrade.plot.plotting calls exit(1) at import time
        # when the optional plotly dependency is missing, and SystemExit is a
        # BaseException that an `except Exception` would let through.
        # KeyboardInterrupt is deliberately not caught.
        msg = f"Cannot import module '{module_path}': {type(e).__name__}: {e}"
        raise ModuleImportError(msg) from e


def _get_class_from_path(class_path: str) -> type[Any]:
    """Import and return a class from a fully-qualified path.

    Args:
        class_path: Validated fully-qualified class path.

    Returns:
        The class object.

    Raises:
        ClassNotFoundError: If the class is not found.
    """
    module_path, class_name = validate_class_path(class_path)
    module = _import_module(module_path)

    cls = getattr(module, class_name, None)
    if cls is None or not isinstance(cls, type):
        msg = f"Class '{class_name}' not found in module '{module_path}'."
        raise ClassNotFoundError(msg)

    result: type[Any] = cls
    return result


def _format_annotation(annotation: Any) -> str:
    """Format a type annotation to a readable string.

    Args:
        annotation: The annotation object from inspect.

    Returns:
        String representation of the annotation.
    """
    if annotation is inspect.Parameter.empty:
        return "Any"
    if isinstance(annotation, type):
        return annotation.__qualname__
    return str(annotation)


def _format_default(default: Any) -> str | None:
    """Format a parameter default value.

    Args:
        default: The default value from inspect.

    Returns:
        String representation or None if no default.
    """
    if default is inspect.Parameter.empty:
        return None
    return repr(default)


def _extract_parameter_info(param: inspect.Parameter) -> ParameterInfo:
    """Extract parameter information from an inspect.Parameter.

    Args:
        param: The parameter to inspect.

    Returns:
        ParameterInfo model.
    """
    return ParameterInfo(
        name=param.name,
        annotation=_format_annotation(param.annotation),
        default=_format_default(param.default),
        kind=param.kind.name,
    )


def _get_first_docstring_line(docstring: str | None) -> str:
    """Extract the first non-empty line from a docstring.

    Args:
        docstring: Full docstring or None.

    Returns:
        First line summary or empty string.
    """
    if not docstring:
        return ""
    for line in docstring.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _get_source_file(obj: Any) -> str | None:
    """Get the source file of an object, relative to freqtrade.

    Args:
        obj: Object to inspect.

    Returns:
        Relative source file path or None.
    """
    try:
        source_file = inspect.getfile(obj)
    except (TypeError, OSError):
        return None

    # Make it relative if possible
    # Anchor on the real package directory. Searching for the first
    # "/freqtrade/" in the absolute path breaks whenever an ancestor directory
    # is named freqtrade — the layout freqtrade's own docs and Docker image
    # use — and would report e.g. "freqtrade/.venv/lib/.../interface.py".
    try:
        package_root = _freqtrade_package_root().parent
        return str(Path(source_file).relative_to(package_root))
    except (ModuleImportError, ValueError):
        # Outside the freqtrade package: return the bare filename rather than
        # leaking an absolute filesystem path.
        return Path(source_file).name


# --- Public API ---


@ttl_cache()
def get_istrategy_class() -> type[Any]:
    """Get the IStrategy class from freqtrade.

    Returns:
        The IStrategy class.

    Raises:
        IntrospectionError: If IStrategy cannot be loaded.
    """
    return _get_class_from_path(ISTRATEGY_CLASS_PATH)


@ttl_cache()
def list_strategy_methods(filter_str: str | None = None) -> list[MethodSummary]:
    """List overridable methods from IStrategy.

    Args:
        filter_str: Optional filter keyword (e.g., 'entry', 'exit', 'indicator').

    Returns:
        List of method summaries.
    """
    validated_filter: str | None = None
    if filter_str:
        validated_filter = validate_filter_string(filter_str, label="method filter")

    cls = get_istrategy_class()
    methods: list[MethodSummary] = []

    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        # Skip private/dunder methods
        if name.startswith("_"):
            continue

        brief = _get_first_docstring_line(inspect.getdoc(method))
        is_callback = name in STRATEGY_CALLBACKS

        # Apply filter
        if validated_filter:
            searchable = f"{name} {brief}".lower()
            if validated_filter not in searchable:
                continue

        methods.append(MethodSummary(name=name, brief=brief, is_callback=is_callback))

    methods.sort(key=lambda m: m.name)
    return methods


@ttl_cache()
def get_method_signature(method_name: str) -> MethodSignature:
    """Get full signature details of an IStrategy method.

    Args:
        method_name: Validated method name.

    Returns:
        Detailed method signature.

    Raises:
        MethodNotFoundError: If the method is not found on IStrategy.
    """
    validate_identifier(method_name, label="method name")
    cls = get_istrategy_class()

    method = getattr(cls, method_name, None)
    if method is None or not callable(method):
        msg = f"Method '{method_name}' not found on IStrategy."
        raise MethodNotFoundError(msg)

    sig = inspect.signature(method)
    parameters = [_extract_parameter_info(p) for p in sig.parameters.values()]
    return_type = _format_annotation(sig.return_annotation)
    docstring = inspect.getdoc(method)
    source_file = _get_source_file(method)

    return MethodSignature(
        name=method_name,
        parameters=parameters,
        return_type=return_type,
        docstring=docstring,
        source_file=source_file,
    )


@ttl_cache()
def get_class_info(class_path: str) -> ClassInfo:
    """Inspect a freqtrade class.

    Args:
        class_path: Fully-qualified class path.

    Returns:
        Class introspection result.
    """
    cls = _get_class_from_path(class_path)
    module_path, class_name = validate_class_path(class_path)

    # MRO
    mro = [c.__qualname__ for c in inspect.getmro(cls)]

    # Public methods
    public_methods = sorted(
        name
        for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    )

    # Class attributes (non-method, non-private)
    class_attrs: dict[str, str] = {}
    for name in sorted(dir(cls)):
        if name.startswith("_"):
            continue
        val = getattr(cls, name, None)
        if callable(val) and not isinstance(val, property):
            continue
        if isinstance(val, property):
            class_attrs[name] = "property"
        else:
            class_attrs[name] = f"{type(val).__name__}: {val!r}"

    return ClassInfo(
        name=class_name,
        module=module_path,
        docstring=inspect.getdoc(cls),
        method_resolution_order=mro,
        public_methods=public_methods,
        class_attributes=class_attrs,
    )


@ttl_cache()
def list_enums(filter_str: str | None = None) -> list[EnumSummary]:
    """List trading-related enums from freqtrade.

    Args:
        filter_str: Optional filter pattern.

    Returns:
        List of enum summaries.
    """
    validated_filter: str | None = None
    if filter_str:
        validated_filter = validate_filter_string(filter_str, label="enum filter")

    enums: list[EnumSummary] = []

    # Scan the freqtrade.enums module
    try:
        enums_module = _import_module("freqtrade.enums")
    except ModuleImportError:
        logger.warning("freqtrade.enums module not found")
        return enums

    for name in dir(enums_module):
        if name.startswith("_"):
            continue
        obj = getattr(enums_module, name)
        if not (isinstance(obj, type) and issubclass(obj, enum.Enum) and obj is not enum.Enum):
            continue

        if validated_filter:
            searchable = f"{name} {inspect.getdoc(obj) or ''}".lower()
            if validated_filter not in searchable:
                continue

        enums.append(
            EnumSummary(
                name=name,
                module=obj.__module__,
                docstring=_get_first_docstring_line(inspect.getdoc(obj)),
                member_count=len(obj),
            )
        )

    enums.sort(key=lambda e: e.name)
    return enums


@ttl_cache()
def get_enum_values(enum_path: str) -> EnumDetail:
    """Get all members of a specific enum.

    Args:
        enum_path: Fully-qualified enum path.

    Returns:
        Detailed enum information with all members.

    Raises:
        ClassNotFoundError: If the enum is not found.
        IntrospectionError: If the target is not an Enum subclass.
    """
    cls = _get_class_from_path(enum_path)
    module_path, enum_name = validate_class_path(enum_path)

    if not (isinstance(cls, type) and issubclass(cls, enum.Enum)):
        msg = f"'{enum_path}' is not an Enum subclass."
        raise IntrospectionError(msg)

    members = [EnumMember(name=member.name, value=repr(member.value)) for member in cls]

    return EnumDetail(
        name=enum_name,
        module=module_path,
        docstring=inspect.getdoc(cls),
        members=members,
    )


@ttl_cache()
def search_codebase(
    query: str,
    max_results: int = DEFAULT_SYMBOL_SEARCH_RESULTS,
) -> SymbolSearchResult:
    """Search for symbols in the freqtrade codebase by name pattern.

    Searches a statically built index (see :mod:`freqtrade_mcp.symbols`), so no
    freqtrade module is imported and no optional dependency can break the scan.
    Modules whose source could not be parsed are reported in
    ``skipped_modules`` rather than dropped silently, and the match count is
    reported separately from the (capped) list of returned symbols.

    Args:
        query: Validated regex search pattern.
        max_results: Maximum number of symbols to return.

    Returns:
        Search result with matches, truncation state, and skipped modules.

    Raises:
        ModuleImportError: If the freqtrade package cannot be located.
    """
    pattern = validate_search_pattern(query)
    capped_results = max(1, min(max_results, MAX_SYMBOL_SEARCH_RESULTS))

    index = build_symbol_index()
    matches = [symbol for symbol in index.symbols if pattern.search(symbol.name)]
    returned = matches[:capped_results]

    if index.unreadable_modules:
        logger.warning(
            "Symbol search results are incomplete: %d module(s) could not be parsed.",
            len(index.unreadable_modules),
        )

    return SymbolSearchResult(
        matches=returned,
        returned=len(returned),
        total_matches=len(matches),
        truncated=len(matches) > len(returned),
        skipped_modules=index.unreadable_modules[:MAX_REPORTED_SKIPPED_MODULES],
        skipped_module_count=len(index.unreadable_modules),
    )


def get_callback_info(callback_name: str) -> CallbackInfo:
    """Get detailed information about a strategy callback method.

    Args:
        callback_name: Validated callback name.

    Returns:
        Detailed callback information.

    Raises:
        MethodNotFoundError: If the callback is not found.
    """
    validate_identifier(callback_name, label="callback name")

    cls = get_istrategy_class()
    method = getattr(cls, callback_name, None)
    if method is None or not callable(method):
        msg = (
            f"Callback '{callback_name}' not found on IStrategy. "
            f"Known callbacks: {', '.join(STRATEGY_CALLBACKS)}"
        )
        raise MethodNotFoundError(msg)

    sig = inspect.signature(method)
    parameters = [_extract_parameter_info(p) for p in sig.parameters.values()]
    return_type = _format_annotation(sig.return_annotation)
    docstring = inspect.getdoc(method)

    return CallbackInfo(
        name=callback_name,
        signature=str(sig),
        parameters=parameters,
        return_type=return_type,
        docstring=docstring,
    )


def get_config_schema(section: str | None = None) -> list[ConfigKey]:
    """Return known configuration keys and descriptions.

    Args:
        section: Optional section filter.

    Returns:
        List of config key entries.
    """
    validated_section: str | None = None
    if section:
        validated_section = validate_filter_string(section, label="config section")

    # Try to get config keys from freqtrade's configuration module
    config_keys: list[ConfigKey] = []

    # Always include known top-level sections
    for key, description in CONFIG_SECTIONS.items():
        if validated_section and validated_section not in key.lower():
            continue
        config_keys.append(ConfigKey(key=key, description=description))

    # Try to extract more config info from freqtrade.configuration if available
    try:
        config_mod = _import_module("freqtrade.configuration")
        for name in sorted(dir(config_mod)):
            if name.startswith("_"):
                continue
            obj = getattr(config_mod, name, None)
            if isinstance(obj, dict) and name.upper() == name:
                if validated_section and validated_section not in name.lower():
                    continue
                config_keys.append(
                    ConfigKey(
                        key=name,
                        description=f"Configuration constant: {name} ({len(obj)} entries)",
                    )
                )
    except ModuleImportError:
        pass

    return config_keys


def get_dataframe_columns(context: str | None = None) -> list[DataframeColumn]:
    """List common DataFrame columns available in strategy methods.

    Args:
        context: Optional context filter ('ohlcv', 'entry', 'exit', 'indicators').

    Returns:
        List of DataFrame column entries.
    """
    validated_context: str | None = None
    if context:
        validated_context = validate_filter_string(context, label="dataframe context")

    columns: list[DataframeColumn] = []

    for ctx_name, ctx_columns in DATAFRAME_CONTEXTS.items():
        if validated_context and validated_context != ctx_name:
            continue
        for col_name, col_desc in ctx_columns.items():
            columns.append(DataframeColumn(name=col_name, description=col_desc, context=ctx_name))

    # Conventional indicator names — these columns exist only if the strategy computes them
    if validated_context == "indicators" or validated_context is None:
        indicator_columns = {
            "rsi": "Relative Strength Index (float64)",
            "macd": "MACD line (float64)",
            "macdsignal": "MACD signal line (float64)",
            "macdhist": "MACD histogram (float64)",
            "bb_upperband": "Bollinger Band upper (float64)",
            "bb_middleband": "Bollinger Band middle/SMA (float64)",
            "bb_lowerband": "Bollinger Band lower (float64)",
            "sma": "Simple Moving Average (float64)",
            "ema": "Exponential Moving Average (float64)",
            "sar": "Parabolic SAR (float64)",
            "adx": "Average Directional Index (float64)",
            "stochrsi": "Stochastic RSI (float64)",
            "atr": "Average True Range (float64)",
            "obv": "On-Balance Volume (float64)",
            "mfi": "Money Flow Index (float64)",
            "cci": "Commodity Channel Index (float64)",
        }
        for col_name, col_desc in indicator_columns.items():
            columns.append(
                DataframeColumn(
                    name=col_name,
                    description=f"{col_desc} — conventional name; present only if the "
                    "strategy computes it in populate_indicators",
                    context="indicators",
                )
            )

    return columns
