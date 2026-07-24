"""Tests for the static (ast-based) symbol index."""

import sys
from pathlib import Path

import pytest

from freqtrade_mcp.exceptions import ModuleImportError
from freqtrade_mcp.symbols import (
    _freqtrade_package_root,
    _module_path_for_file,
    build_symbol_index,
)


class TestModulePathForFile:
    """Tests for _module_path_for_file."""

    def test_plain_module(self) -> None:
        """A regular file maps to a dotted module path."""
        root = Path("/pkgs/freqtrade")
        path = root / "strategy" / "interface.py"
        assert _module_path_for_file(path, root) == "freqtrade.strategy.interface"

    def test_package_init(self) -> None:
        """__init__.py maps to the package itself."""
        root = Path("/pkgs/freqtrade")
        assert _module_path_for_file(root / "strategy" / "__init__.py", root) == (
            "freqtrade.strategy"
        )

    def test_root_init(self) -> None:
        """The root __init__.py maps to the top-level package."""
        root = Path("/pkgs/freqtrade")
        assert _module_path_for_file(root / "__init__.py", root) == "freqtrade"


class TestBuildSymbolIndex:
    """Tests for build_symbol_index against a fake source tree."""

    def test_finds_definitions_with_kinds(self, fake_freqtrade_source: Path) -> None:
        """Classes, enums, functions and constants are classified."""
        index = build_symbol_index()
        found = {(s.name, s.module): s.kind for s in index.symbols}

        assert found[("IStrategy", "freqtrade.strategy.interface")] == "class"
        assert found[("helper", "freqtrade.strategy.interface")] == "function"
        assert found[("async_helper", "freqtrade.strategy.interface")] == "function"
        assert found[("MAX_RETRIES", "freqtrade.strategy.interface")] == "constant"
        assert found[("TIMEFRAME", "freqtrade.strategy.interface")] == "constant"
        assert found[("SignalDirection", "freqtrade.enums")] == "enum"
        assert found[("RunMode", "freqtrade.enums")] == "enum"

    def test_excludes_private_symbols(self, fake_freqtrade_source: Path) -> None:
        """Underscore-prefixed names stay out of the index."""
        names = {s.name for s in build_symbol_index().symbols}
        assert "_Private" not in names
        assert "_hidden" not in names
        assert "_INTERNAL" not in names

    def test_includes_public_reexports(self, fake_freqtrade_source: Path) -> None:
        """A package __init__ re-export is indexed under the package path.

        Strategy code imports from `freqtrade.strategy`, not from the
        definition site, so both paths should be discoverable.
        """
        index = build_symbol_index()
        modules = {s.module for s in index.symbols if s.name == "IStrategy"}
        assert modules == {"freqtrade.strategy.interface", "freqtrade.strategy"}

        reexport = next(
            s for s in index.symbols if s.name == "IStrategy" and s.module == "freqtrade.strategy"
        )
        assert reexport.kind == "class", "kind is recovered from the definition site"

    def test_ignores_private_and_external_reexports(self, fake_freqtrade_source: Path) -> None:
        """Private names and non-freqtrade imports are not re-exported."""
        index = build_symbol_index()
        entries = {(s.name, s.module) for s in index.symbols}
        assert ("_Private", "freqtrade.strategy") not in entries
        assert ("path", "freqtrade.strategy") not in entries

    def test_reports_unparseable_modules(self, fake_freqtrade_source: Path) -> None:
        """A file with a syntax error is reported, not silently skipped."""
        index = build_symbol_index()
        assert "freqtrade.broken" in index.unreadable_modules

    def test_imports_nothing(self, fake_freqtrade_source: Path) -> None:
        """Building the index must not import any freqtrade module.

        Importing the tree pulled ccxt, pandas and sqlalchemy into the server
        process and ran third-party top-level code.
        """
        before = {name for name in sys.modules if name.startswith("freqtrade.")}
        build_symbol_index()
        after = {name for name in sys.modules if name.startswith("freqtrade.")}
        assert after == before

    def test_results_are_sorted(self, fake_freqtrade_source: Path) -> None:
        """Symbols come back in a stable order."""
        symbols = build_symbol_index().symbols
        assert symbols == sorted(symbols, key=lambda s: (s.name, s.module))


class TestFreqtradePackageRoot:
    """Tests for _freqtrade_package_root."""

    def test_raises_when_package_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing freqtrade package produces an actionable error."""
        import importlib.util

        monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
        with pytest.raises(ModuleImportError, match="Cannot locate"):
            _freqtrade_package_root()
