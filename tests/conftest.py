"""Shared test fixtures for freqtrade-mcp tests."""

import enum
import types
from pathlib import Path
from typing import Any, ClassVar

import pytest


class FakeSignalDirection(enum.Enum):
    """Fake SignalDirection for testing."""

    LONG = "long"
    SHORT = "short"


class FakeTradeExitType(enum.Enum):
    """Fake TradeExitType for testing."""

    STOP_LOSS = "stop_loss"
    TRAILING_STOP_LOSS = "trailing_stop_loss"
    ROI = "roi"
    EXIT_SIGNAL = "exit_signal"
    FORCE_EXIT = "force_exit"
    CUSTOM_EXIT = "custom_exit"


class FakeIStrategy:
    """Fake IStrategy class for testing introspection.

    This class mimics the structure of freqtrade's IStrategy
    for unit testing without requiring freqtrade to be installed.
    """

    timeframe: str = "5m"
    minimal_roi: ClassVar[dict[str, float]] = {}
    stoploss: float = -0.10

    def bot_start(self) -> None:
        """Called once at bot startup."""

    def bot_loop_start(self) -> None:
        """Called at the start of each bot loop iteration."""

    def populate_indicators(self, dataframe: Any, metadata: dict[str, Any]) -> Any:
        """Populate indicators in the DataFrame.

        Args:
            dataframe: OHLCV DataFrame.
            metadata: Pair metadata dictionary.

        Returns:
            DataFrame with indicators added.
        """
        return dataframe

    def populate_entry_trend(self, dataframe: Any, metadata: dict[str, Any]) -> Any:
        """Populate entry signals in the DataFrame.

        Args:
            dataframe: DataFrame with indicators.
            metadata: Pair metadata dictionary.

        Returns:
            DataFrame with entry signals.
        """
        return dataframe

    def populate_exit_trend(self, dataframe: Any, metadata: dict[str, Any]) -> Any:
        """Populate exit signals in the DataFrame.

        Args:
            dataframe: DataFrame with indicators.
            metadata: Pair metadata dictionary.

        Returns:
            DataFrame with exit signals.
        """
        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade: Any,
        current_time: Any,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> float:
        """Calculate custom stoploss value.

        Args:
            pair: Trading pair.
            trade: Trade object.
            current_time: Current datetime.
            current_rate: Current rate.
            current_profit: Current profit ratio.
            **kwargs: Additional keyword arguments.

        Returns:
            Desired stoploss value.
        """
        return -0.10

    def custom_exit(
        self,
        pair: str,
        trade: Any,
        current_time: Any,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | bool:
        """Determine custom exit conditions.

        Args:
            pair: Trading pair.
            trade: Trade object.
            current_time: Current datetime.
            current_rate: Current rate.
            current_profit: Current profit ratio.
            **kwargs: Additional keyword arguments.

        Returns:
            Exit reason string or False to not exit.
        """
        return False

    def informative_pairs(self) -> list[tuple[str, str]]:
        """Define additional informative pairs for the strategy.

        Returns:
            List of (pair, timeframe) tuples.
        """
        return []

    def _private_method(self) -> None:
        """Private method that should not appear in public API."""


def _fake_helper() -> None:
    """Public function re-exported by the fake root module."""


def _create_fake_freqtrade_module() -> types.ModuleType:
    """Create a fake freqtrade module hierarchy for testing."""
    # Root module
    ft = types.ModuleType("freqtrade")
    ft.__version__ = "2026.3"  # type: ignore[attr-defined]
    ft.__path__ = []  # type: ignore[attr-defined]

    # Public symbols used by the live-introspection unit tests.
    ft.IStrategy = FakeIStrategy  # type: ignore[attr-defined]
    ft.SignalDirection = FakeSignalDirection  # type: ignore[attr-defined]
    ft.TradeExitType = FakeTradeExitType  # type: ignore[attr-defined]
    ft.fake_helper = _fake_helper  # type: ignore[attr-defined]
    ft.DEFAULT_TIMEFRAME = "5m"  # type: ignore[attr-defined]

    # Strategy module
    ft_strategy = types.ModuleType("freqtrade.strategy")
    ft_strategy.__path__ = []  # type: ignore[attr-defined]

    # Strategy interface module
    ft_strategy_interface = types.ModuleType("freqtrade.strategy.interface")
    ft_strategy_interface.IStrategy = FakeIStrategy  # type: ignore[attr-defined]

    # Enums module
    ft_enums = types.ModuleType("freqtrade.enums")
    ft_enums.__path__ = []  # type: ignore[attr-defined]
    ft_enums.SignalDirection = FakeSignalDirection  # type: ignore[attr-defined]
    ft_enums.TradeExitType = FakeTradeExitType  # type: ignore[attr-defined]

    # Configuration module
    ft_config = types.ModuleType("freqtrade.configuration")
    ft_config.__path__ = []  # type: ignore[attr-defined]
    ft_config.AVAILABLE_CLI_OPTIONS = {"option1": "desc1", "option2": "desc2"}  # type: ignore[attr-defined]

    return ft


@pytest.fixture
def fake_freqtrade_modules(monkeypatch: pytest.MonkeyPatch) -> dict[str, types.ModuleType]:
    """Register fake freqtrade modules in sys.modules for testing."""
    import sys

    ft = _create_fake_freqtrade_module()
    ft_strategy = types.ModuleType("freqtrade.strategy")
    ft_strategy.__path__ = []  # type: ignore[attr-defined]
    ft_strategy_interface = types.ModuleType("freqtrade.strategy.interface")
    ft_strategy_interface.IStrategy = FakeIStrategy  # type: ignore[attr-defined]
    ft_enums = types.ModuleType("freqtrade.enums")
    ft_enums.__path__ = []  # type: ignore[attr-defined]
    ft_enums.SignalDirection = FakeSignalDirection  # type: ignore[attr-defined]
    ft_enums.TradeExitType = FakeTradeExitType  # type: ignore[attr-defined]
    ft_config = types.ModuleType("freqtrade.configuration")
    ft_config.__path__ = []  # type: ignore[attr-defined]
    ft_config.AVAILABLE_CLI_OPTIONS = {"option1": "desc1"}  # type: ignore[attr-defined]
    ft_config_schema = types.ModuleType("freqtrade.config_schema")
    ft_config_schema.CONF_SCHEMA = {  # type: ignore[attr-defined]
        "properties": {
            "exchange": {
                "description": "Exchange configuration.",
                "$ref": "#/definitions/exchange",
            },
            "pairlists": {"description": "Configuration for pairlists.", "type": "array"},
            "stoploss": {"description": "Stoploss ratio.", "type": "number"},
            "strategy": {"type": "string"},
        },
        "required": ["exchange"],
    }

    modules = {
        "freqtrade": ft,
        "freqtrade.strategy": ft_strategy,
        "freqtrade.strategy.interface": ft_strategy_interface,
        "freqtrade.enums": ft_enums,
        "freqtrade.configuration": ft_config,
        "freqtrade.config_schema": ft_config_schema,
    }

    for name, mod in modules.items():
        monkeypatch.setitem(sys.modules, name, mod)

    return modules


@pytest.fixture
def fake_docs_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with sample markdown docs for testing."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    (docs_dir / "strategy-callbacks.md").write_text(
        "# Strategy Callbacks\n\n"
        "Callbacks are called whenever needed.\n\n"
        "## bot_start\n\nCalled once at startup.\n\n"
        "## custom_stoploss\n\nCalculate custom stoploss.\n"
    )
    (docs_dir / "configuration.md").write_text(
        "# Configure the bot\n\n"
        "Freqtrade has many configurable features.\n\n"
        "## Configuration file\n\nThe bot uses JSON config.\n"
    )
    (docs_dir / "backtesting.md").write_text(
        "# Backtesting\n\nValidate your strategy with backtesting.\n\nRequires historic data.\n"
    )

    commands_dir = docs_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "backtesting.md").write_text(
        "# Backtesting Command\n\n```\nusage: freqtrade backtesting [-h]\n```\n"
    )
    (commands_dir / "trade.md").write_text(
        "# Trade Command\n\n```\nusage: freqtrade trade [-h]\n```\n"
    )

    return docs_dir


@pytest.fixture
def fake_freqtrade_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake freqtrade source tree on disk for the symbol index.

    The symbol index parses files rather than importing modules, so it needs
    real source files — the in-memory modules of ``fake_freqtrade_modules`` are
    invisible to it.
    """
    from freqtrade_mcp import symbols

    root = tmp_path / "site-packages" / "freqtrade"
    (root / "strategy").mkdir(parents=True)

    (root / "__init__.py").write_text('__version__ = "2026.6"\n')

    # Public re-exports, the documented import path for strategy code.
    (root / "strategy" / "__init__.py").write_text(
        "from freqtrade.strategy.interface import IStrategy\n"
        "from freqtrade.strategy.helpers import merge_informative_pair\n"
        "from freqtrade.strategy.interface import _Private\n"
        "from os import path\n"
    )
    (root / "strategy" / "interface.py").write_text(
        '"""Strategy interface."""\n\n'
        "class IStrategy:\n"
        "    pass\n\n"
        "class _Private:\n"
        "    pass\n\n"
        "def helper():\n"
        "    pass\n\n"
        "def _hidden():\n"
        "    pass\n\n"
        "async def async_helper():\n"
        "    pass\n\n"
        "MAX_RETRIES = 3\n"
        "_INTERNAL = 1\n"
        "TIMEFRAME: str = '5m'\n"
    )
    (root / "strategy" / "helpers.py").write_text(
        "def merge_informative_pair():\n    pass\n",
    )
    (root / "enums.py").write_text(
        "from enum import Enum\n\n"
        "class SignalDirection(str, Enum):\n"
        "    LONG = 'long'\n\n"
        "class RunMode(Enum):\n"
        "    LIVE = 'live'\n",
    )
    # Unparseable on purpose: must be reported, not silently dropped.
    (root / "broken.py").write_text("def oops(:\n")

    monkeypatch.setattr(symbols, "_freqtrade_package_root", lambda: root)
    return root


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Clear all TTL caches between tests."""
    from freqtrade_mcp.cache import get_cache
    from freqtrade_mcp.docs import _load_docs_index
    from freqtrade_mcp.introspection import (
        get_callback_info,
        get_class_info,
        get_config_schema,
        get_enum_values,
        get_istrategy_class,
        get_method_signature,
        list_enums,
        list_strategy_methods,
        search_codebase,
    )
    from freqtrade_mcp.symbols import build_symbol_index

    get_cache().clear()

    # Clear per-function caches
    for fn in [
        get_istrategy_class,
        list_strategy_methods,
        get_method_signature,
        get_class_info,
        get_config_schema,
        get_callback_info,
        list_enums,
        get_enum_values,
        search_codebase,
        build_symbol_index,
        _load_docs_index,
    ]:
        if hasattr(fn, "cache"):
            fn.cache.clear()  # type: ignore[union-attr]
