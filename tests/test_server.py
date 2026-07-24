"""MCP server integration tests.

Every tool is an async coroutine: FastMCP runs synchronous tool functions
inline on the event loop, so the blocking work is offloaded to a worker thread
instead. Tests therefore await the tools directly (pytest-asyncio auto mode).
"""

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from freqtrade_mcp.constants import ENV_LOG_LEVEL
from freqtrade_mcp.server import (
    _configure_logging,
    freqtrade_get_callback_info,
    freqtrade_get_class_info,
    freqtrade_get_config_schema,
    freqtrade_get_dataframe_columns,
    freqtrade_get_doc,
    freqtrade_get_enum_values,
    freqtrade_get_method_signature,
    freqtrade_get_version_info,
    freqtrade_list_docs,
    freqtrade_list_enums,
    freqtrade_list_strategy_methods,
    freqtrade_search_codebase,
    freqtrade_search_docs,
)


class TestListStrategyMethodsTool:
    """Tests for freqtrade_list_strategy_methods tool."""

    async def test_returns_list_of_dicts(self, fake_freqtrade_modules: Any) -> None:
        """Should return list of dictionaries."""
        result = await freqtrade_list_strategy_methods()
        assert isinstance(result, list)
        assert len(result) > 0
        assert isinstance(result[0], dict)
        assert "name" in result[0]
        assert "brief" in result[0]
        assert "is_callback" in result[0]

    async def test_with_filter(self, fake_freqtrade_modules: Any) -> None:
        """Should accept filter parameter."""
        result = await freqtrade_list_strategy_methods(filter="entry")
        assert isinstance(result, list)
        names = [m["name"] for m in result]
        assert "populate_entry_trend" in names

    async def test_with_none_filter(self, fake_freqtrade_modules: Any) -> None:
        """Should work with None filter."""
        result = await freqtrade_list_strategy_methods(filter=None)
        assert isinstance(result, list)
        assert len(result) > 0


class TestGetMethodSignatureTool:
    """Tests for freqtrade_get_method_signature tool."""

    async def test_returns_dict(self, fake_freqtrade_modules: Any) -> None:
        """Should return a dictionary with signature details."""
        result = await freqtrade_get_method_signature(method_name="populate_indicators")
        assert isinstance(result, dict)
        assert result["name"] == "populate_indicators"
        assert "parameters" in result
        assert "return_type" in result
        assert "docstring" in result

    async def test_parameters_structure(self, fake_freqtrade_modules: Any) -> None:
        """Parameters should have proper structure."""
        result = await freqtrade_get_method_signature(method_name="populate_indicators")
        params = result["parameters"]
        assert isinstance(params, list)
        for p in params:
            assert "name" in p
            assert "annotation" in p
            assert "kind" in p


class TestGetClassInfoTool:
    """Tests for freqtrade_get_class_info tool."""

    async def test_returns_dict(self, fake_freqtrade_modules: Any) -> None:
        """Should return a dictionary with class info."""
        result = await freqtrade_get_class_info(
            class_path="freqtrade.strategy.interface.IStrategy"
        )
        assert isinstance(result, dict)
        assert result["name"] == "IStrategy"
        assert "method_resolution_order" in result
        assert "public_methods" in result
        assert "class_attributes" in result


class TestListEnumsTool:
    """Tests for freqtrade_list_enums tool."""

    async def test_returns_list_of_dicts(self, fake_freqtrade_modules: Any) -> None:
        """Should return list of enum dictionaries."""
        result = await freqtrade_list_enums()
        assert isinstance(result, list)
        assert len(result) >= 2
        for item in result:
            assert "name" in item
            assert "module" in item
            assert "member_count" in item


class TestGetEnumValuesTool:
    """Tests for freqtrade_get_enum_values tool."""

    async def test_returns_dict(self, fake_freqtrade_modules: Any) -> None:
        """Should return dict with enum members."""
        result = await freqtrade_get_enum_values(enum_path="freqtrade.enums.SignalDirection")
        assert isinstance(result, dict)
        assert result["name"] == "SignalDirection"
        assert len(result["members"]) == 2


class TestSearchCodebaseTool:
    """Tests for freqtrade_search_codebase tool."""

    async def test_returns_structured_result(self, fake_freqtrade_modules: Any) -> None:
        """Should return a completeness-aware result envelope."""
        result = await freqtrade_search_codebase(query="Signal")
        assert isinstance(result, dict)
        assert isinstance(result["matches"], list)
        assert result["returned"] == len(result["matches"])
        assert result["total_matches"] >= result["returned"]
        assert isinstance(result["truncated"], bool)
        assert isinstance(result["skipped_modules"], list)
        assert result["skipped_module_count"] >= len(result["skipped_modules"])

    async def test_respects_max_results(self, fake_freqtrade_modules: Any) -> None:
        """Should cap the number of returned symbols and flag truncation."""
        unlimited = await freqtrade_search_codebase(query=".*", max_results=500)
        assert unlimited["total_matches"] >= 2, "fixture should expose several symbols"

        capped = await freqtrade_search_codebase(query=".*", max_results=1)
        assert capped["returned"] == 1
        assert capped["total_matches"] == unlimited["total_matches"]
        assert capped["truncated"] is True

    async def test_not_truncated_when_all_returned(self, fake_freqtrade_modules: Any) -> None:
        """Truncated must be False when every match fits in the response."""
        result = await freqtrade_search_codebase(query=".*", max_results=500)
        assert result["truncated"] is False
        assert result["returned"] == result["total_matches"]

    async def test_rejects_out_of_range_max_results(self, fake_freqtrade_modules: Any) -> None:
        """max_results outside 1-500 should be rejected by validation."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            await freqtrade_search_codebase(query="Signal", max_results=0)
        with pytest.raises(PydanticValidationError):
            await freqtrade_search_codebase(query="Signal", max_results=501)


class TestGetCallbackInfoTool:
    """Tests for freqtrade_get_callback_info tool."""

    async def test_returns_dict(self, fake_freqtrade_modules: Any) -> None:
        """Should return callback info dict."""
        result = await freqtrade_get_callback_info(callback_name="custom_stoploss")
        assert isinstance(result, dict)
        assert result["name"] == "custom_stoploss"
        assert "signature" in result
        assert "parameters" in result
        assert "docstring" in result


class TestGetConfigSchemaTool:
    """Tests for freqtrade_get_config_schema tool."""

    async def test_returns_list(self, fake_freqtrade_modules: Any) -> None:
        """Should return list of config keys."""
        result = await freqtrade_get_config_schema()
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "key" in item
            assert "description" in item

    async def test_with_section_filter(self, fake_freqtrade_modules: Any) -> None:
        """Should accept section filter."""
        result = await freqtrade_get_config_schema(section="exchange")
        assert isinstance(result, list)


class TestGetDataframeColumnsTool:
    """Tests for freqtrade_get_dataframe_columns tool."""

    async def test_returns_list(self) -> None:
        """Should return list of column entries."""
        result = await freqtrade_get_dataframe_columns()
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "name" in item
            assert "description" in item
            assert "context" in item

    async def test_with_context_filter(self) -> None:
        """Should accept context filter."""
        result = await freqtrade_get_dataframe_columns(context="ohlcv")
        names = [c["name"] for c in result]
        assert "open" in names
        assert "close" in names


class TestGetVersionInfoTool:
    """Tests for freqtrade_get_version_info tool."""

    async def test_returns_version_dict(self) -> None:
        """Should return version info dictionary."""
        with patch("freqtrade_mcp.server.check_freqtrade_version", return_value="2026.3"):
            result = await freqtrade_get_version_info()
            assert isinstance(result, dict)
            assert "mcp_server_version" in result
            assert "freqtrade_version" in result
            assert "python_version" in result
            assert result["freqtrade_version"] == "2026.3"


class TestListDocsTool:
    """Tests for freqtrade_list_docs tool."""

    async def test_returns_list_when_available(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = await freqtrade_list_docs()
        assert isinstance(result, list)
        assert len(result) == 5
        topics = [t["topic"] for t in result]
        assert "strategy-callbacks" in topics
        assert "commands/backtesting" in topics

    async def test_returns_error_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        result = await freqtrade_list_docs()
        assert isinstance(result, dict)
        assert "error" in result

    async def test_with_filter(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = await freqtrade_list_docs(filter="strategy")
        assert isinstance(result, list)
        assert len(result) >= 1


class TestSearchDocsTool:
    """Tests for freqtrade_search_docs tool."""

    async def test_returns_list_when_available(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = await freqtrade_search_docs(query="stoploss")
        assert isinstance(result, list)
        assert len(result) >= 1

    async def test_returns_error_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        result = await freqtrade_search_docs(query="anything")
        assert isinstance(result, dict)
        assert "error" in result

    async def test_with_max_results(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = await freqtrade_search_docs(query="the", max_results=1)
        assert isinstance(result, list)
        assert len(result) <= 1


class TestGetDocTool:
    """Tests for freqtrade_get_doc tool."""

    async def test_returns_dict_when_available(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = await freqtrade_get_doc(topic="strategy-callbacks")
        assert isinstance(result, dict)
        assert result["topic"] == "strategy-callbacks"
        assert "content" in result

    async def test_returns_error_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        result = await freqtrade_get_doc(topic="strategy-callbacks")
        assert isinstance(result, dict)
        assert "error" in result

    async def test_topic_not_found(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        from freqtrade_mcp.exceptions import DocTopicNotFoundError

        with pytest.raises(DocTopicNotFoundError):
            await freqtrade_get_doc(topic="nonexistent-topic")


class TestConfigureLogging:
    """Tests for _configure_logging."""

    @pytest.fixture(autouse=True)
    def _restore_logger(self) -> Iterator[None]:
        """Restore the package logger state after each test."""
        pkg_logger = logging.getLogger("freqtrade_mcp")
        handlers = list(pkg_logger.handlers)
        level = pkg_logger.level
        propagate = pkg_logger.propagate
        yield
        pkg_logger.handlers = handlers
        pkg_logger.setLevel(level)
        pkg_logger.propagate = propagate

    def test_sets_requested_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid level name should be applied, case-insensitively."""
        monkeypatch.setenv(ENV_LOG_LEVEL, "debug")
        _configure_logging()
        assert logging.getLogger("freqtrade_mcp").level == logging.DEBUG

    def test_unknown_level_falls_back_without_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A module attribute that is not a level must not crash the server.

        ``getattr(logging, "BASIC_FORMAT")`` returns a format string, and
        feeding that to setLevel() raises ValueError at startup.
        """
        monkeypatch.setenv(ENV_LOG_LEVEL, "BASIC_FORMAT")
        _configure_logging()
        assert logging.getLogger("freqtrade_mcp").level == logging.WARNING

    def test_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Repeated calls must not stack handlers."""
        monkeypatch.setenv(ENV_LOG_LEVEL, "INFO")
        _configure_logging()
        _configure_logging()
        _configure_logging()
        assert len(logging.getLogger("freqtrade_mcp").handlers) == 1

    def test_does_not_propagate_to_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Propagation must stay off so records cannot reach a stdout handler."""
        monkeypatch.setenv(ENV_LOG_LEVEL, "INFO")
        _configure_logging()
        assert logging.getLogger("freqtrade_mcp").propagate is False
