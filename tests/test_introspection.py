"""Tests for the introspection engine."""

import sys
from pathlib import Path
from typing import Any

import pytest

from freqtrade_mcp.constants import MAX_SYMBOL_SEARCH_RESULTS
from freqtrade_mcp.exceptions import (
    ClassNotFoundError,
    IntrospectionError,
    MethodNotFoundError,
    ModuleImportError,
    ValidationError,
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

    def test_import_failure_is_not_reported_as_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A broken installation should raise instead of looking enum-free."""

        def fail_import(_module_path: str) -> None:
            raise ModuleImportError("broken enum import")

        monkeypatch.setattr("freqtrade_mcp.introspection._import_module", fail_import)
        with pytest.raises(ModuleImportError, match="broken enum import"):
            list_enums()


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
        """Should return every property from the live schema."""
        keys = get_config_schema()
        assert {item.key for item in keys} == {"exchange", "pairlists", "stoploss", "strategy"}
        assert all(isinstance(k, ConfigKey) for k in keys)
        exchange = next(item for item in keys if item.key == "exchange")
        assert exchange.description.endswith("Required.")

    def test_filter_by_section(self, fake_freqtrade_modules: Any) -> None:
        """Should filter by section keyword."""
        keys = get_config_schema(section="exchange")
        assert len(keys) > 0
        assert all(
            "exchange" in k.key.lower() or "exchange" in k.description.lower() for k in keys
        )

    def test_description_falls_back_to_schema_type(self, fake_freqtrade_modules: Any) -> None:
        """Properties without descriptions should still be useful."""
        keys = get_config_schema(section="strategy")
        assert len(keys) == 1
        assert keys[0].description == "Freqtrade configuration key 'strategy' (string)."

    def test_schema_failure_is_not_silently_replaced(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing schema modules should produce an actionable error."""

        def fail_import(_module_path: str) -> None:
            raise ModuleImportError("schema unavailable")

        monkeypatch.setattr("freqtrade_mcp.introspection._import_module", fail_import)
        with pytest.raises(IntrospectionError, match="Cannot load"):
            get_config_schema()


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
        """Invalid context should list the supported options."""
        with pytest.raises(ValidationError, match="Expected one of"):
            get_dataframe_columns(context="nonexistent")


class TestSearchCodebase:
    """Tests for search_codebase.

    The search runs against the statically built symbol index, so these use the
    fake *source tree* fixture rather than the in-memory module fixture.
    """

    def test_search_finds_class(self, fake_freqtrade_source: Path) -> None:
        """Should find classes matching a pattern."""
        result = search_codebase("IStrategy")
        assert isinstance(result, SymbolSearchResult)
        assert any(m.name == "IStrategy" for m in result.matches)

    def test_search_returns_symbol_matches(self, fake_freqtrade_source: Path) -> None:
        """Results should be SymbolMatch instances with a known kind."""
        result = search_codebase(".*")
        assert result.matches
        for r in result.matches:
            assert isinstance(r, SymbolMatch)
            assert r.kind in {"class", "function", "constant", "enum"}

    def test_reports_truncation(self, fake_freqtrade_source: Path) -> None:
        """A capped search must report the full match count and truncation."""
        full = search_codebase(".*", max_results=MAX_SYMBOL_SEARCH_RESULTS)
        assert full.truncated is False
        assert full.returned == full.total_matches

        capped = search_codebase(".*", max_results=1)
        assert capped.returned == 1
        assert len(capped.matches) == 1
        assert capped.total_matches == full.total_matches
        assert capped.truncated is True

    def test_max_results_is_clamped(self, fake_freqtrade_source: Path) -> None:
        """Out-of-range values are clamped rather than trusted blindly."""
        result = search_codebase(".*", max_results=10_000)
        assert result.returned <= MAX_SYMBOL_SEARCH_RESULTS

    def test_reports_unparseable_modules(self, fake_freqtrade_source: Path) -> None:
        """Modules that cannot be parsed must be reported, not dropped silently."""
        result = search_codebase(".*")
        assert "freqtrade.broken" in result.skipped_modules
        assert result.skipped_module_count == 1
        # The rest of the tree was still indexed.
        assert result.total_matches > 0

    def test_broken_module_does_not_abort_search(self, fake_freqtrade_source: Path) -> None:
        """A syntax error in one file must not fail the whole search.

        The previous implementation imported every module: a failure in one of
        them (or a module calling exit() when an optional dependency was
        missing) aborted the entire tool call.
        """
        result = search_codebase("IStrategy")
        assert any(m.name == "IStrategy" for m in result.matches)

    def test_search_is_case_insensitive(self, fake_freqtrade_source: Path) -> None:
        """Patterns are compiled with IGNORECASE."""
        assert search_codebase("istrategy").total_matches > 0

    def test_no_module_is_imported(self, fake_freqtrade_source: Path) -> None:
        """Searching must not import anything from the freqtrade namespace."""
        before = {name for name in sys.modules if name.startswith("freqtrade.")}
        search_codebase(".*")
        assert {name for name in sys.modules if name.startswith("freqtrade.")} == before
