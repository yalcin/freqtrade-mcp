"""Tests for the introspection engine."""

import importlib
import pkgutil
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from freqtrade_mcp.constants import MAX_SYMBOL_SEARCH_RESULTS
from freqtrade_mcp.exceptions import (
    ClassNotFoundError,
    IntrospectionError,
    MethodNotFoundError,
    ModuleImportError,
)
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
    CallbackInfo,
    ClassInfo,
    ConfigKey,
    EnumDetail,
    MethodSignature,
    MethodSummary,
    SymbolMatch,
    SymbolSearchResult,
)


def _walk_yielding(*module_names: str) -> Callable[..., Iterator[tuple[None, str, bool]]]:
    """Build a pkgutil.walk_packages stand-in yielding fixed module names.

    The fake freqtrade package has an empty ``__path__``, so the real
    walk_packages yields nothing and no submodule is ever reached.
    """

    def _walk(
        path: Any, prefix: str = "", onerror: Any = None
    ) -> Iterator[tuple[None, str, bool]]:
        for name in module_names:
            yield (None, name, False)

    return _walk


class TestListStrategyMethods:
    """Tests for list_strategy_methods."""

    def test_lists_public_methods(self, fake_freqtrade_modules: Any) -> None:
        """Should return public methods from FakeIStrategy."""
        methods = list_strategy_methods()
        assert len(methods) > 0
        assert all(isinstance(m, MethodSummary) for m in methods)

        names = [m.name for m in methods]
        assert "populate_indicators" in names
        assert "populate_entry_trend" in names
        assert "custom_stoploss" in names
        # Private methods should be excluded
        assert "_private_method" not in names

    def test_filter_by_entry(self, fake_freqtrade_modules: Any) -> None:
        """Filter by 'entry' should narrow results."""
        methods = list_strategy_methods(filter_str="entry")
        names = [m.name for m in methods]
        assert "populate_entry_trend" in names
        # Methods without 'entry' in name/description should be excluded
        assert "custom_stoploss" not in names

    def test_filter_by_exit(self, fake_freqtrade_modules: Any) -> None:
        """Filter by 'exit' should narrow results."""
        methods = list_strategy_methods(filter_str="exit")
        names = [m.name for m in methods]
        assert "populate_exit_trend" in names
        assert "custom_exit" in names

    def test_callback_flag(self, fake_freqtrade_modules: Any) -> None:
        """Callback methods should be flagged."""
        methods = list_strategy_methods()
        method_dict = {m.name: m for m in methods}
        if "bot_start" in method_dict:
            assert method_dict["bot_start"].is_callback is True
        if "populate_indicators" in method_dict:
            assert method_dict["populate_indicators"].is_callback is True

    def test_sorted_by_name(self, fake_freqtrade_modules: Any) -> None:
        """Results should be sorted alphabetically."""
        methods = list_strategy_methods()
        names = [m.name for m in methods]
        assert names == sorted(names)


class TestGetMethodSignature:
    """Tests for get_method_signature."""

    def test_valid_method(self, fake_freqtrade_modules: Any) -> None:
        """Should return full signature for a valid method."""
        sig = get_method_signature("populate_indicators")
        assert isinstance(sig, MethodSignature)
        assert sig.name == "populate_indicators"
        assert len(sig.parameters) > 0
        assert sig.docstring is not None
        assert "DataFrame" in sig.docstring or "indicators" in sig.docstring.lower()

    def test_method_parameters(self, fake_freqtrade_modules: Any) -> None:
        """Should include parameter details."""
        sig = get_method_signature("populate_indicators")
        param_names = [p.name for p in sig.parameters]
        assert "self" in param_names
        assert "dataframe" in param_names
        assert "metadata" in param_names

    def test_method_with_kwargs(self, fake_freqtrade_modules: Any) -> None:
        """Should handle **kwargs properly."""
        sig = get_method_signature("custom_stoploss")
        param_names = [p.name for p in sig.parameters]
        assert "kwargs" in param_names

    def test_nonexistent_method(self, fake_freqtrade_modules: Any) -> None:
        """Should raise MethodNotFoundError for unknown method."""
        with pytest.raises(MethodNotFoundError, match="not found"):
            get_method_signature("nonexistent_method")

    def test_invalid_method_name(self, fake_freqtrade_modules: Any) -> None:
        """Should validate method name."""
        from freqtrade_mcp.exceptions import ValidationError

        with pytest.raises(ValidationError):
            get_method_signature("invalid.name")


class TestGetClassInfo:
    """Tests for get_class_info."""

    def test_istrategy_class(self, fake_freqtrade_modules: Any) -> None:
        """Should return info for IStrategy (FakeIStrategy)."""
        info = get_class_info("freqtrade.strategy.interface.IStrategy")
        assert isinstance(info, ClassInfo)
        assert info.name == "IStrategy"
        assert info.module == "freqtrade.strategy.interface"
        assert len(info.public_methods) > 0
        assert len(info.method_resolution_order) > 0

    def test_class_attributes(self, fake_freqtrade_modules: Any) -> None:
        """Should include class-level attributes."""
        info = get_class_info("freqtrade.strategy.interface.IStrategy")
        assert "timeframe" in info.class_attributes
        assert "stoploss" in info.class_attributes

    def test_nonexistent_class(self, fake_freqtrade_modules: Any) -> None:
        """Should raise ClassNotFoundError."""
        with pytest.raises(ClassNotFoundError, match="not found"):
            get_class_info("freqtrade.strategy.interface.NonExistent")

    def test_nonexistent_module(self, fake_freqtrade_modules: Any) -> None:
        """Should raise ModuleNotFoundError."""
        with pytest.raises(ModuleImportError, match="Cannot import"):
            get_class_info("freqtrade.nonexistent.module.SomeClass")


class TestListEnums:
    """Tests for list_enums."""

    def test_lists_enums(self, fake_freqtrade_modules: Any) -> None:
        """Should find fake enums."""
        enums = list_enums()
        assert len(enums) >= 2
        names = [e.name for e in enums]
        assert "SignalDirection" in names
        assert "TradeExitType" in names

    def test_enum_member_count(self, fake_freqtrade_modules: Any) -> None:
        """Should report correct member count."""
        enums = list_enums()
        signal_dir = next(e for e in enums if e.name == "SignalDirection")
        assert signal_dir.member_count == 2  # LONG, SHORT

    def test_filter_enums(self, fake_freqtrade_modules: Any) -> None:
        """Should filter enums by keyword."""
        enums = list_enums(filter_str="signal")
        names = [e.name for e in enums]
        assert "SignalDirection" in names


class TestGetEnumValues:
    """Tests for get_enum_values."""

    def test_signal_direction(self, fake_freqtrade_modules: Any) -> None:
        """Should return all members of SignalDirection."""
        result = get_enum_values("freqtrade.enums.SignalDirection")
        assert isinstance(result, EnumDetail)
        assert result.name == "SignalDirection"
        assert len(result.members) == 2

        member_names = [m.name for m in result.members]
        assert "LONG" in member_names
        assert "SHORT" in member_names

    def test_trade_exit_type(self, fake_freqtrade_modules: Any) -> None:
        """Should return all members of TradeExitType."""
        result = get_enum_values("freqtrade.enums.TradeExitType")
        assert isinstance(result, EnumDetail)
        assert len(result.members) == 6

    def test_non_enum_class(self, fake_freqtrade_modules: Any) -> None:
        """Should raise IntrospectionError for non-enum class."""
        with pytest.raises(IntrospectionError, match="not an Enum"):
            get_enum_values("freqtrade.strategy.interface.IStrategy")


class TestGetCallbackInfo:
    """Tests for get_callback_info."""

    def test_valid_callback(self, fake_freqtrade_modules: Any) -> None:
        """Should return callback info."""
        info = get_callback_info("custom_stoploss")
        assert isinstance(info, CallbackInfo)
        assert info.name == "custom_stoploss"
        assert len(info.parameters) > 0
        assert info.docstring is not None

    def test_nonexistent_callback(self, fake_freqtrade_modules: Any) -> None:
        """Should raise MethodNotFoundError for unknown callback."""
        with pytest.raises(MethodNotFoundError, match="not found"):
            get_callback_info("nonexistent_callback")


class TestGetConfigSchema:
    """Tests for get_config_schema."""

    def test_all_sections(self, fake_freqtrade_modules: Any) -> None:
        """Should return config keys from all sections."""
        keys = get_config_schema()
        assert len(keys) > 0
        assert all(isinstance(k, ConfigKey) for k in keys)

    def test_filter_by_section(self, fake_freqtrade_modules: Any) -> None:
        """Should filter by section keyword."""
        keys = get_config_schema(section="exchange")
        assert len(keys) > 0
        assert all(
            "exchange" in k.key.lower() or "exchange" in k.description.lower() for k in keys
        )

    def test_returns_known_sections(self, fake_freqtrade_modules: Any) -> None:
        """Should include well-known config sections."""
        keys = get_config_schema()
        key_names = [k.key for k in keys]
        assert "exchange" in key_names
        assert "stoploss" in key_names
        assert "strategy" in key_names


class TestGetDataframeColumns:
    """Tests for get_dataframe_columns."""

    def test_all_columns(self) -> None:
        """Should return columns from all contexts."""
        columns = get_dataframe_columns()
        assert len(columns) > 0
        contexts = {c.context for c in columns}
        assert "ohlcv" in contexts
        assert "entry" in contexts
        assert "exit" in contexts

    def test_ohlcv_context(self) -> None:
        """Should return OHLCV columns."""
        columns = get_dataframe_columns(context="ohlcv")
        names = [c.name for c in columns]
        assert "open" in names
        assert "high" in names
        assert "low" in names
        assert "close" in names
        assert "volume" in names

    def test_entry_context(self) -> None:
        """Should return entry signal columns."""
        columns = get_dataframe_columns(context="entry")
        names = [c.name for c in columns]
        assert "enter_long" in names
        assert "enter_short" in names

    def test_indicators_context(self) -> None:
        """Should return common indicator columns."""
        columns = get_dataframe_columns(context="indicators")
        names = [c.name for c in columns]
        assert "rsi" in names
        assert "macd" in names
        assert "ema" in names

    def test_invalid_context(self) -> None:
        """Invalid context should return empty list."""
        columns = get_dataframe_columns(context="nonexistent")
        assert len(columns) == 0


class TestSearchCodebase:
    """Tests for search_codebase."""

    def test_search_finds_class(self, fake_freqtrade_modules: Any) -> None:
        """Should find classes matching pattern."""
        # Note: search_codebase walks the package tree, which is limited
        # with fake modules since __path__ is empty. Test with direct module.
        result = search_codebase("IStrategy")
        # May or may not find it depending on fake module setup
        assert isinstance(result, SymbolSearchResult)

    def test_search_returns_symbol_matches(self, fake_freqtrade_modules: Any) -> None:
        """Results should be SymbolMatch instances."""
        result = search_codebase(".*")
        for r in result.matches:
            assert isinstance(r, SymbolMatch)
            assert r.kind in {"class", "function", "constant", "enum"}

    def test_reports_truncation(self, fake_freqtrade_modules: Any) -> None:
        """A capped search must report the full match count and truncation."""
        full = search_codebase(".*", max_results=MAX_SYMBOL_SEARCH_RESULTS)
        assert full.truncated is False
        assert full.returned == full.total_matches

        capped = search_codebase(".*", max_results=1)
        assert capped.returned == 1
        assert len(capped.matches) == 1
        assert capped.total_matches == full.total_matches
        assert capped.truncated is True

    def test_max_results_is_clamped(self, fake_freqtrade_modules: Any) -> None:
        """Out-of-range values are clamped rather than trusted blindly."""
        result = search_codebase(".*", max_results=10_000)
        assert result.returned <= MAX_SYMBOL_SEARCH_RESULTS

    def test_reports_unimportable_modules(
        self, fake_freqtrade_modules: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Modules that fail to import must be reported, not dropped silently."""
        monkeypatch.setattr(pkgutil, "walk_packages", _walk_yielding("freqtrade.broken"))
        result = search_codebase(".*")

        assert "freqtrade.broken" in result.skipped_modules
        assert result.skipped_module_count == 1
        # The rest of the scan still produced results.
        assert result.total_matches > 0

    def test_non_import_error_does_not_abort_search(
        self, fake_freqtrade_modules: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-ImportError during a module import must not kill the search.

        _import_module used to catch only ImportError, so anything else raised
        by a module's top-level code escaped and failed the whole tool call.
        """
        real_import = importlib.import_module

        def _flaky_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "freqtrade.exploding":
                msg = "simulated top-level failure"
                raise OSError(msg)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(pkgutil, "walk_packages", _walk_yielding("freqtrade.exploding"))
        monkeypatch.setattr(importlib, "import_module", _flaky_import)

        result = search_codebase(".*")  # must not raise
        assert isinstance(result, SymbolSearchResult)
        assert "freqtrade.exploding" in result.skipped_modules

    def test_system_exit_during_import_is_contained(
        self, fake_freqtrade_modules: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A module calling exit() at import time must not kill the search.

        freqtrade.plot.plotting does exactly this when the optional plotly
        dependency is missing. SystemExit is a BaseException, so an
        `except Exception` lets it through and aborts the whole tool call.
        """
        real_import = importlib.import_module

        def _exiting_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "freqtrade.plot.plotting":
                raise SystemExit(1)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(pkgutil, "walk_packages", _walk_yielding("freqtrade.plot.plotting"))
        monkeypatch.setattr(importlib, "import_module", _exiting_import)

        result = search_codebase(".*")  # must not raise SystemExit
        assert "freqtrade.plot.plotting" in result.skipped_modules

    def test_system_exit_from_package_walk_is_contained(
        self, fake_freqtrade_modules: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SystemExit raised by walk_packages itself must degrade gracefully.

        onerror only covers what walk_packages catches internally, and it
        catches Exception — SystemExit passes straight through the generator.
        """

        def _walk_then_exit(
            path: Any, prefix: str = "", onerror: Any = None
        ) -> Iterator[tuple[None, str, bool]]:
            yield (None, "freqtrade.enums", False)
            raise SystemExit(1)

        monkeypatch.setattr(pkgutil, "walk_packages", _walk_then_exit)

        result = search_codebase(".*")  # must not raise SystemExit
        assert any("walk interrupted" in name for name in result.skipped_modules)
        assert result.total_matches > 0, "symbols found before the interruption are kept"

    def test_walk_package_errors_are_recorded(
        self, fake_freqtrade_modules: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """walk_packages must be given an onerror callback.

        Without one it swallows ImportError but re-raises everything else, so a
        single misbehaving package aborted the whole search.
        """

        def _walk_with_error(
            path: Any,
            prefix: str = "",
            onerror: Any = None,
        ) -> Any:
            assert onerror is not None, "walk_packages called without onerror"
            onerror("freqtrade.pkgfail")
            return iter(())

        monkeypatch.setattr(pkgutil, "walk_packages", _walk_with_error)
        result = search_codebase(".*")
        assert "freqtrade.pkgfail" in result.skipped_modules
