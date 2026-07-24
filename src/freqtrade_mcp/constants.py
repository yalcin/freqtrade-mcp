"""Constants for freqtrade-mcp."""

import logging
import re
from typing import Final

# Minimum supported freqtrade version
MIN_FREQTRADE_VERSION: Final[str] = "2026.2"

# Default cache TTL in seconds (1 hour)
DEFAULT_CACHE_TTL: Final[int] = 3600

# Maximum number of entries kept per cache. Without a bound, every distinct
# search query holds its full result list for the whole TTL, so a chatty agent
# grows the server's memory unboundedly.
DEFAULT_CACHE_MAXSIZE: Final[int] = 128

# Validation patterns
IDENTIFIER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FILTER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9 _-]+$")
MODULE_PATH_PATTERN: Final[re.Pattern[str]] = re.compile(r"^freqtrade(\.[A-Za-z_][A-Za-z0-9_]*)+$")
SAFE_REGEX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_.*+?^$|()\\[\]{}_ -]+$")

# Maximum length for input strings
MAX_INPUT_LENGTH: Final[int] = 256

# Symbol search result limits. A broad pattern such as ".*" matches every
# public symbol in the freqtrade tree (~2500 entries, >200 KB of JSON), which
# would flood the context window of the calling LLM in a single response.
DEFAULT_SYMBOL_SEARCH_RESULTS: Final[int] = 50
MAX_SYMBOL_SEARCH_RESULTS: Final[int] = 500

# Maximum number of skipped module names reported in a search result.
MAX_REPORTED_SKIPPED_MODULES: Final[int] = 20

# Freqtrade modules allowed for introspection
ALLOWED_TOP_LEVEL_MODULE: Final[str] = "freqtrade"

# IStrategy class path
ISTRATEGY_CLASS_PATH: Final[str] = "freqtrade.strategy.interface.IStrategy"

# Known strategy callback methods (informational, not exhaustive)
STRATEGY_CALLBACKS: Final[tuple[str, ...]] = (
    "bot_start",
    "bot_loop_start",
    "informative_pairs",
    "populate_indicators",
    "populate_entry_trend",
    "populate_exit_trend",
    "custom_stake_amount",
    "custom_exit",
    "custom_exit_price",
    "custom_entry_price",
    "custom_stoploss",
    "confirm_trade_entry",
    "confirm_trade_exit",
    "adjust_trade_position",
    "adjust_entry_price",
    "leverage",
    "order_filled",
    "protection_space",
)

# Known DataFrame column contexts
DATAFRAME_CONTEXTS: Final[dict[str, dict[str, str]]] = {
    "ohlcv": {
        "date": "Candle timestamp (datetime64)",
        "open": "Opening price (float64)",
        "high": "Highest price (float64)",
        "low": "Lowest price (float64)",
        "close": "Closing price (float64)",
        "volume": "Trading volume (float64)",
    },
    "entry": {
        "enter_long": "Long entry signal (int: 0 or 1)",
        "enter_short": "Short entry signal (int: 0 or 1)",
        "enter_tag": "Entry tag string for trade tracking (str, optional)",
    },
    "exit": {
        "exit_long": "Long exit signal (int: 0 or 1)",
        "exit_short": "Short exit signal (int: 0 or 1)",
        "exit_tag": "Exit tag string for trade tracking (str, optional)",
    },
}

# Known top-level config sections with human-readable descriptions
CONFIG_SECTIONS: Final[dict[str, str]] = {
    "exchange": "Exchange connection settings: name, API keys, ccxt options, pair whitelist.",
    "pairlist": "Pairlist handlers that build and filter the tradable pair list "
    "(e.g. StaticPairList, VolumePairList).",
    "stake_currency": "Currency used for trading stakes (e.g. 'USDT').",
    "stake_amount": "Amount of stake_currency per trade, or 'unlimited' to spread the balance.",
    "dry_run": "Simulation mode: true trades with simulated money, false trades live.",
    "trading_mode": "Market type to trade: 'spot', 'margin' or 'futures'.",
    "margin_mode": "Margin mode for leveraged trading: 'isolated' or 'cross'.",
    "strategy": "Name of the strategy class to load.",
    "timeframe": "Candle timeframe (e.g. '5m', '1h'); used if the strategy does not set one.",
    "order_types": "Order type per action: entry, exit, stoploss, stoploss_on_exchange.",
    "order_time_in_force": "Time-in-force per order side (GTC, FOK, IOC, PO).",
    "entry_pricing": "How entry order prices are derived from the orderbook or ticker.",
    "exit_pricing": "How exit order prices are derived from the orderbook or ticker.",
    "minimal_roi": "Minimum ROI thresholds keyed by trade age in minutes; triggers exits.",
    "stoploss": "Stoploss ratio relative to the entry price (e.g. -0.10 for -10%).",
    "trailing_stop": "Trailing stoploss settings (trailing_stop_positive, offset).",
    "unfilledtimeout": "Minutes to wait before cancelling unfilled entry/exit orders.",
    "protections": "Protection plugins (StoplossGuard, CooldownPeriod, MaxDrawdown, ...).",
    "telegram": "Telegram bot notifications and remote control settings.",
    "api_server": "Local REST/WebSocket API server settings (used by FreqUI).",
    "internals": "Bot-internal settings such as process throttling and heartbeat interval.",
    "dataformat_ohlcv": "Storage format for OHLCV data (json, jsongz, feather, parquet).",
    "dataformat_trades": "Storage format for trades data (json, jsongz, feather, parquet).",
}

# Documentation settings
ENV_DOCS_PATH: Final[str] = "FREQTRADE_DOCS_PATH"
DOC_TOPIC_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9_-]*(/[a-zA-Z0-9][a-zA-Z0-9_-]*)*$"
)
DOC_SEARCH_CONTEXT_LINES: Final[int] = 3
MAX_DOC_SEARCH_RESULTS: Final[int] = 50

# Documentation page size limits. Freqtrade's largest pages are ~70 KB
# (strategy-callbacks), i.e. ~17k tokens returned in a single tool response.
DEFAULT_DOC_MAX_CHARS: Final[int] = 20_000
MAX_DOC_MAX_CHARS: Final[int] = 100_000

# Markdown heading prefix that delimits a documentation section.
DOC_SECTION_PREFIX: Final[str] = "## "
DOCS_UNAVAILABLE_MSG: Final[str] = (
    "Freqtrade documentation not available. "
    "Set FREQTRADE_DOCS_PATH environment variable to the freqtrade docs/ directory."
)

# Environment variable names
ENV_LOG_LEVEL: Final[str] = "FREQTRADE_MCP_LOG_LEVEL"

# Log levels accepted in FREQTRADE_MCP_LOG_LEVEL. An explicit allow-list is
# used instead of getattr(logging, name): several module attributes are upper
# case without being levels (BASIC_FORMAT is a format string), and passing one
# of those to setLevel() raises ValueError and kills the server at startup.
LOG_LEVELS: Final[dict[str, int]] = {
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
DEFAULT_LOG_LEVEL: Final[str] = "WARNING"

# Server metadata
SERVER_NAME: Final[str] = "freqtrade-mcp"
SERVER_DESCRIPTION: Final[str] = (
    "Read-only MCP server for Freqtrade codebase introspection. "
    "Helps LLMs write better Freqtrade strategy code by providing access to "
    "method signatures, docstrings, type hints, enums, and configuration schemas."
)
