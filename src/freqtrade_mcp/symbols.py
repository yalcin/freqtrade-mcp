"""Static symbol index for the freqtrade codebase.

The index is built by parsing freqtrade's source files with :mod:`ast` instead
of importing them. Importing the package tree pulled ccxt, pandas and
sqlalchemy into the server process, cost seconds on first use, executed
third-party top-level code (``freqtrade.plot.plotting`` calls ``exit(1)`` when
the optional plotly dependency is missing) and silently lost every module that
failed to import. Parsing the same tree costs a fraction of that, imports
nothing, and cannot be defeated by a missing optional dependency.

Trade-off: only statically declared, top-level symbols are visible. Anything
produced at runtime — dynamic ``globals()`` writes, metaclass-generated
attributes — is not in the index. Live objects are still introspected with
:mod:`inspect` elsewhere in this package, where signatures and docstrings are
needed.
"""

import ast
import importlib.util
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from freqtrade_mcp.cache import ttl_cache
from freqtrade_mcp.constants import ALLOWED_TOP_LEVEL_MODULE
from freqtrade_mcp.exceptions import ModuleImportError
from freqtrade_mcp.models import SymbolMatch

logger = logging.getLogger(__name__)

_INIT_FILENAME = "__init__.py"


@dataclass(frozen=True)
class SymbolIndex:
    """A parsed view of the freqtrade source tree.

    Attributes:
        symbols: Every public top-level symbol found, deduplicated.
        unreadable_modules: Module paths whose source could not be read or
            parsed, and which are therefore missing from ``symbols``.
    """

    symbols: list[SymbolMatch] = field(default_factory=list)
    unreadable_modules: list[str] = field(default_factory=list)


def _freqtrade_package_root() -> Path:
    """Locate the installed freqtrade package directory without importing it.

    Returns:
        Filesystem path of the freqtrade package.

    Raises:
        ModuleImportError: If the package cannot be located.
    """
    try:
        spec = importlib.util.find_spec(ALLOWED_TOP_LEVEL_MODULE)
    except (ImportError, ValueError) as e:
        msg = f"Cannot locate the '{ALLOWED_TOP_LEVEL_MODULE}' package: {e}"
        raise ModuleImportError(msg) from e

    locations = list(spec.submodule_search_locations or []) if spec else []
    if not locations:
        msg = (
            f"Cannot locate the '{ALLOWED_TOP_LEVEL_MODULE}' package on disk. "
            "Install freqtrade in the same environment as freqtrade-mcp."
        )
        raise ModuleImportError(msg)

    return Path(locations[0])


def _module_path_for_file(source_file: Path, root: Path) -> str:
    """Derive a dotted module path from a source file path.

    Args:
        source_file: Path to a ``.py`` file inside the package.
        root: Path of the package root directory.

    Returns:
        Dotted module path (e.g. ``freqtrade.strategy.interface``).
    """
    parts = list(source_file.relative_to(root).parts)
    if parts[-1] == _INIT_FILENAME:
        parts.pop()
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return ".".join([ALLOWED_TOP_LEVEL_MODULE, *parts])


def _base_names(node: ast.ClassDef) -> Iterator[str]:
    """Yield the readable names of a class definition's bases."""
    for base in node.bases:
        if isinstance(base, ast.Name):
            yield base.id
        elif isinstance(base, ast.Attribute):
            yield base.attr


def _class_kind(node: ast.ClassDef) -> str:
    """Classify a class definition as an enum or a plain class.

    Only base *names* are visible statically, so this matches the conventional
    suffix: Enum, IntEnum, StrEnum, ReprEnum.
    """
    return "enum" if any(name.endswith("Enum") for name in _base_names(node)) else "class"


def _iter_definitions(tree: ast.Module, module_path: str) -> Iterator[SymbolMatch]:
    """Yield public symbols defined at the top level of a module."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                yield SymbolMatch(name=node.name, module=module_path, kind=_class_kind(node))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                yield SymbolMatch(name=node.name, module=module_path, kind="function")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    yield SymbolMatch(name=target.id, module=module_path, kind="constant")
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                yield SymbolMatch(name=target.id, module=module_path, kind="constant")


def _resolve_import_source(node: ast.ImportFrom, package_path: str) -> str | None:
    """Resolve the module an ``ImportFrom`` node reads from.

    Args:
        node: The import node.
        package_path: Dotted path of the package holding the ``__init__.py``.

    Returns:
        Dotted module path, or None if it resolves outside freqtrade.
    """
    if node.level == 0:
        source = node.module
    else:
        parts = package_path.split(".")
        drop = node.level - 1
        parts = parts[: len(parts) - drop] if drop < len(parts) else []
        if not parts:
            return None
        source = ".".join([*parts, node.module]) if node.module else ".".join(parts)

    if not source or not source.startswith(f"{ALLOWED_TOP_LEVEL_MODULE}."):
        return None
    return source


def _iter_reexports(
    tree: ast.Module,
    package_path: str,
    kinds: dict[tuple[str, str], str],
) -> Iterator[SymbolMatch]:
    """Yield symbols re-exported by a package's ``__init__.py``.

    Strategy code imports from the documented public path
    (``from freqtrade.strategy import IStrategy``), not from the definition
    site, so both are worth surfacing. The kind is recovered by looking the
    name up where it was defined; unresolvable names are skipped rather than
    reported with a guessed kind.
    """
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        source = _resolve_import_source(node, package_path)
        if source is None:
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            exported = alias.asname or alias.name
            if exported.startswith("_"):
                continue
            kind = kinds.get((source, alias.name))
            if kind is None:
                continue
            yield SymbolMatch(name=exported, module=package_path, kind=kind)


@ttl_cache()
def build_symbol_index() -> SymbolIndex:
    """Parse the freqtrade source tree into a searchable symbol index.

    Returns:
        The symbol index, including any modules that could not be parsed.

    Raises:
        ModuleImportError: If the freqtrade package cannot be located.
    """
    root = _freqtrade_package_root()

    parsed: list[tuple[str, ast.Module, Path]] = []
    unreadable: list[str] = []

    for source_file in sorted(root.rglob("*.py")):
        module_path = _module_path_for_file(source_file, root)
        try:
            tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as e:
            logger.warning("Cannot parse %s: %s: %s", source_file, type(e).__name__, e)
            unreadable.append(module_path)
            continue
        parsed.append((module_path, tree, source_file))

    # First pass: definitions. Re-exports are resolved against these, so they
    # have to be complete before the second pass runs.
    symbols: dict[tuple[str, str, str], SymbolMatch] = {}
    kinds: dict[tuple[str, str], str] = {}
    for module_path, tree, _source_file in parsed:
        for symbol in _iter_definitions(tree, module_path):
            symbols[(symbol.name, symbol.module, symbol.kind)] = symbol
            kinds[(symbol.module, symbol.name)] = symbol.kind

    # Second pass: public re-exports from package __init__ files.
    for module_path, tree, source_file in parsed:
        if source_file.name != _INIT_FILENAME:
            continue
        for symbol in _iter_reexports(tree, module_path, kinds):
            symbols.setdefault((symbol.name, symbol.module, symbol.kind), symbol)

    index = SymbolIndex(
        symbols=sorted(symbols.values(), key=lambda s: (s.name, s.module)),
        unreadable_modules=sorted(unreadable),
    )
    logger.info(
        "Indexed %d symbols from %d modules (%d unreadable)",
        len(index.symbols),
        len(parsed),
        len(index.unreadable_modules),
    )
    return index
