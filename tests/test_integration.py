"""Smoke tests against a real, importable freqtrade installation.

The rest of the suite runs on fake modules built in conftest.py, which is fast
and hermetic but blind to everything that only happens against the real
package: import failures, path layout, the size of a full symbol scan. These
tests fill that gap and are skipped when freqtrade is not importable.

Run them explicitly with:  pytest -m integration
"""

import sys

import pytest

from freqtrade_mcp.constants import ISTRATEGY_CLASS_PATH, MAX_SYMBOL_SEARCH_RESULTS
from freqtrade_mcp.introspection import (
    get_class_info,
    get_istrategy_class,
    get_method_signature,
    list_strategy_methods,
    search_codebase,
)
from freqtrade_mcp.models import SymbolSearchResult
from freqtrade_mcp.symbols import build_symbol_index

pytestmark = pytest.mark.integration

# Skips the whole module when freqtrade is absent or its install is incomplete.
pytest.importorskip(
    ISTRATEGY_CLASS_PATH.rsplit(".", maxsplit=1)[0],
    reason="requires a complete freqtrade installation",
)


class TestRealIStrategy:
    """Introspection against the real IStrategy class."""

    def test_istrategy_loads(self) -> None:
        """The real IStrategy class should be importable."""
        cls = get_istrategy_class()
        assert cls.__name__ == "IStrategy"

    def test_known_callbacks_are_present(self) -> None:
        """Callbacks listed in STRATEGY_CALLBACKS should exist on the real class."""
        names = {m.name for m in list_strategy_methods()}
        for expected in ("populate_indicators", "populate_entry_trend", "custom_stoploss"):
            assert expected in names, f"{expected} missing from the real IStrategy"

    def test_populate_indicators_signature(self) -> None:
        """The real signature should expose the documented parameters."""
        sig = get_method_signature("populate_indicators")
        param_names = [p.name for p in sig.parameters]
        assert "dataframe" in param_names
        assert "metadata" in param_names

    def test_source_file_is_relative_and_plausible(self) -> None:
        """source_file must be a relative path inside the freqtrade package.

        _get_source_file anchors on the first '/freqtrade/' in the absolute
        path, so any ancestor directory named 'freqtrade' (the layout used by
        freqtrade's own docs and Docker image) produces a bogus path. Fake
        modules have no source file at all, so only a real install catches it.
        """
        source_file = get_method_signature("populate_indicators").source_file
        assert source_file is not None
        assert not source_file.startswith("/"), f"leaked an absolute path: {source_file}"
        assert source_file.startswith("freqtrade/"), f"unexpected anchor: {source_file}"
        assert "site-packages" not in source_file, f"path not relative to package: {source_file}"

    def test_class_info_on_real_class(self) -> None:
        """Class introspection should resolve the real MRO."""
        info = get_class_info(ISTRATEGY_CLASS_PATH)
        assert info.name == "IStrategy"
        assert "IStrategy" in info.method_resolution_order
        assert len(info.public_methods) > 10


class TestRealSymbolSearch:
    """Symbol search against the real freqtrade package tree."""

    def test_search_is_capped_and_reports_totals(self) -> None:
        """A wildcard search must stay bounded and report what it left out."""
        result = search_codebase(".*", max_results=10)
        assert isinstance(result, SymbolSearchResult)
        assert result.returned == 10
        assert len(result.matches) == 10
        assert result.total_matches > 10, "the real tree should expose many symbols"
        assert result.truncated is True

    def test_response_size_stays_reasonable(self) -> None:
        """The capped payload must be small enough for an LLM context window.

        Uncapped, '.*' returned ~2500 symbols and >200 KB of JSON in a single
        tool response.
        """
        payload = search_codebase(".*", max_results=50).model_dump_json()
        assert len(payload) < 50_000, f"payload too large: {len(payload)} bytes"

    def test_finds_a_known_symbol(self) -> None:
        """A specific known freqtrade symbol should be findable."""
        result = search_codebase("IStrategy", max_results=MAX_SYMBOL_SEARCH_RESULTS)
        assert any(m.name == "IStrategy" for m in result.matches)

    def test_skipped_modules_are_reported(self) -> None:
        """Skipped modules must be counted, whether or not any were skipped."""
        result = search_codebase("Trade", max_results=20)
        assert result.skipped_module_count == 0 or result.skipped_modules
        assert result.skipped_module_count >= len(result.skipped_modules)

    def test_search_imports_no_freqtrade_module(self) -> None:
        """Searching the real tree must not import any freqtrade module.

        The previous implementation walked and imported the package, pulling
        ccxt, pandas and sqlalchemy into the server process and executing
        third-party top-level code on the way.
        """
        before = {name for name in sys.modules if name.startswith("freqtrade.")}
        search_codebase("Exchange", max_results=5)
        after = {name for name in sys.modules if name.startswith("freqtrade.")}
        assert after == before

    def test_optional_dependencies_do_not_break_the_scan(self) -> None:
        """Modules guarded by optional dependencies must still be indexed.

        freqtrade.plot.plotting calls exit(1) at import time when plotly is
        absent, which used to abort the whole search.
        """
        index = build_symbol_index()
        modules = {symbol.module for symbol in index.symbols}
        assert "freqtrade.plot.plotting" in modules

    def test_public_reexports_are_discoverable(self) -> None:
        """The documented import path should be findable too.

        Strategy code says `from freqtrade.strategy import IStrategy`, not the
        definition site `freqtrade.strategy.interface`.
        """
        result = search_codebase("IStrategy", max_results=MAX_SYMBOL_SEARCH_RESULTS)
        modules = {m.module for m in result.matches if m.name == "IStrategy"}
        assert "freqtrade.strategy" in modules
        assert "freqtrade.strategy.interface" in modules
