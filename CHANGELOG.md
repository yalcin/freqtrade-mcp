# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-08

### Changed (symbol search and documentation)

- `freqtrade_search_codebase` now searches a **static index built with `ast`**
  instead of importing the freqtrade package tree. Against freqtrade 2026.6 the
  first search went from ~2s warm (9-21s cold) to **0.37s**, imports **zero**
  freqtrade modules (previously ~250, pulling in ccxt, pandas and sqlalchemy),
  and reports **zero** skipped modules where the import-based scan silently lost
  36 of them to missing optional dependencies. Symbols re-exported from a
  package `__init__` are indexed too, so the documented import path
  (`freqtrade.strategy.IStrategy`) is discoverable alongside the definition site
  (`freqtrade.strategy.interface.IStrategy`).
  Limitation: only statically declared, top-level symbols are visible; anything
  created at runtime is not. Live objects are still introspected with `inspect`
  where signatures and docstrings are needed.
- The depth limit that silently hid modules more than four levels deep is gone —
  it existed to bound import cost that no longer exists.
- `freqtrade_get_doc` returns pages in slices and can return a single section.
  It gained `section`, `offset` and `max_chars` (default 20000), and the
  response now carries `sections`, `offset`, `returned_chars`, `total_chars`,
  `truncated` and `next_offset`. `strategy-callbacks` used to arrive as 69 KB
  (~17k tokens) in one response; it is now ~5k tokens per slice, and asking for
  one of its 14 sections costs as little as ~90 tokens. **Breaking change** for
  anyone relying on `content` always holding the whole page.

### Fixed (correctness)

- `source_file` no longer reports a bogus path. It was derived from the first
  `/freqtrade/` found in the absolute path, so any ancestor directory named
  `freqtrade` — the layout freqtrade's own docs and Docker image use — produced
  e.g. `freqtrade/.venv/lib/.../interface.py`. It is now computed relative to
  the real package directory, and falls back to the bare filename instead of
  leaking an absolute path.
- Version comparison uses `packaging.version` (PEP 440) instead of a hand-rolled
  numeric-prefix parser that mapped `2026.2rc1` onto `(2026, 2)`, letting a
  release candidate pass as its final release. A version that cannot be parsed
  now logs a warning and starts anyway, rather than being silently mangled.
- `TTLCache` is bounded (`maxsize`, default 128, LRU eviction). Expired entries
  are only dropped when their key is read again, so without a bound every
  distinct query held its full result list for the whole hour-long TTL.
- Symbol search now accepts a safe glob-style language (`*`, `?`, and optional
  boundary anchors) and escapes every literal before compiling it. The previous
  regex character whitelist still admitted nested quantifiers and was vulnerable
  to catastrophic backtracking.
- Configuration discovery now reads the installed freqtrade `CONF_SCHEMA`
  instead of returning a stale 23-key table. Import failures are reported
  explicitly, as are invalid enum and DataFrame-context requests.
- Regression tests cover event-loop offloading and the real installed
  configuration schema; the test suite now enforces at least 90% coverage.
- Import failures, static parse warnings, and documentation discovery logs no
  longer include raw exception text or absolute filesystem paths.
- Source distributions exclude local GitNexus indexes and generated agent
  instruction files, preventing workspace analysis artifacts from being shipped.
- The MCP SDK dependency is constrained to the compatible 1.x line; MCP 2.0
  renamed `FastMCP` to `MCPServer` and requires a separate migration.

### Fixed

- Tools no longer block the server. FastMCP calls synchronous tool functions
  inline on the event loop, so every blocking import or file read stalled the
  whole server — the first symbol search alone held it for seconds, during
  which no other call, keepalive or cancellation could be processed. All tools
  are now coroutines that offload their work to a worker thread.
- `freqtrade_search_codebase` no longer aborts when part of the freqtrade tree
  fails to import. `pkgutil.walk_packages` was called without `onerror`, which
  makes it re-raise anything that is not an `ImportError`, and `_import_module`
  itself only caught `ImportError`. Both now handle any exception *and*
  `SystemExit` — `freqtrade.plot.plotting` calls `exit(1)` at import time when
  the optional plotly dependency is missing, which a plain `except Exception`
  does not catch.
- Startup now verifies that `freqtrade.strategy.interface` actually imports and
  says so up front. `check_freqtrade_version` only reads distribution metadata,
  which stays valid on an installation that cannot be imported, so the server
  used to start silently and then fail on every introspection call.
  The check is a **warning, not a fatal error**: freqtrade declares `scipy`
  only under its `hyperopt` extra while `freqtrade.data.metrics` imports it
  unconditionally, so a stock `pip install freqtrade` genuinely cannot import
  the strategy interface. Symbol search reads the source statically and the
  documentation tools never touch freqtrade, so the server stays useful; the
  warning names the affected tools and the fix
  (`pip install freqtrade[hyperopt]`).
- An unknown `FREQTRADE_MCP_LOG_LEVEL` no longer crashes the server at startup.
  The level was resolved with `getattr(logging, name)`, which happily returns
  non-level attributes such as `BASIC_FORMAT`; `setLevel` then raised
  `ValueError`. Levels are now resolved from an explicit allow-list.

### Changed

- `freqtrade_search_codebase` returns a result envelope instead of a bare list:
  `matches`, `returned`, `total_matches`, `truncated`, `skipped_modules` and
  `skipped_module_count`. Results are capped by a new `max_results` parameter
  (1-500, default 50). A `.*` query previously returned ~2500 symbols and over
  200 KB of JSON in a single response, and silently omitted every module that
  failed to import. **Breaking change** for anyone consuming the old list shape.
- Logging setup is idempotent (repeated calls no longer stack handlers) and the
  `freqtrade_mcp` logger no longer propagates to the root logger, so a root
  handler attached to stdout cannot corrupt the JSON-RPC stream.

### Added

- `tests/test_integration.py`: smoke tests against a real freqtrade
  installation, skipped when freqtrade is not importable. The rest of the suite
  runs on fake modules and is blind to import failures and path layout — this
  is what surfaced the `SystemExit` bug above. Run with `pytest -m integration`.
- `freqtrade_mcp.symbols`: the static symbol index described above.
- CI installs `freqtrade[hyperopt]` and runs the integration tests as a
  separate step that **fails if they were skipped**. Without the extra they
  skipped silently, so the only tests exercising the live package never ran.
- `anyio` and `packaging` are now explicit dependencies (previously only
  transitive, via `mcp` and `freqtrade` respectively).

### Changed

- CI: bump actions/checkout to v5 and actions/setup-python to v6 (Node 24 runners)
- Tool parameters now expose descriptions and constraints in the MCP schema via annotated Pydantic fields
- `freqtrade_get_config_schema` returns meaningful descriptions for known config sections instead of placeholders
- `freqtrade_get_dataframe_columns` marks "indicators" columns as conventional names that only exist if the strategy computes them
- `None` results (e.g. the docs index when docs are unavailable) are now cached, avoiding repeated re-scans and log spam
- Log output is serialized with `json.dumps`, so messages containing quotes no longer produce invalid JSON
- Faster duplicate detection in `freqtrade_search_codebase`

### Fixed

- Filter parameters now accept hyphens and spaces, so hyphenated doc topics (e.g. `strategy-callbacks`) and multi-word filters work; values are stripped and whitespace-only input is rejected
- Changelog link in package metadata pointed to a nonexistent `main` branch
- CI workflow triggered on the nonexistent `main` branch, so it never ran; now targets `master`

### Removed

- Dead code: unused `_discover_submodules` and `find_enums_in_module` helpers

## [0.1.1] - 2026-05-09

### Added

- 3 new documentation tools for accessing freqtrade markdown docs:
  - `freqtrade_list_docs` — list available documentation topics with optional filter
  - `freqtrade_search_docs` — full-text search across all docs with AND semantics
  - `freqtrade_get_doc` — read a specific documentation page by topic name
- `FREQTRADE_DOCS_PATH` environment variable to configure docs directory
- Graceful degradation when docs are not available (server continues, tools return guidance)
- TTL-cached documentation index with automatic refresh
- Input validation for doc topics (path traversal prevention) and search queries
- `DocTopicNotFoundError` with close-match suggestions
- 47 new tests for documentation functionality

### Changed

- Clarified the intended MCP usage philosophy: read-only reference layer, public API first, and no reliance on undocumented Freqtrade internals in generated strategy code.

## [0.1.0] - 2026-03-03

### Added

- Initial release of freqtrade-mcp
- 10 read-only MCP tools for Freqtrade codebase introspection:
  - `freqtrade_list_strategy_methods` — list overridable IStrategy methods
  - `freqtrade_get_method_signature` — get full method signatures
  - `freqtrade_get_class_info` — inspect freqtrade classes
  - `freqtrade_list_enums` — list trading-related enums
  - `freqtrade_get_enum_values` — get enum member values
  - `freqtrade_search_codebase` — search symbols by pattern
  - `freqtrade_get_callback_info` — get strategy callback details
  - `freqtrade_get_config_schema` — browse configuration keys
  - `freqtrade_get_dataframe_columns` — list DataFrame columns
  - `freqtrade_get_version_info` — version information
- Input validation with regex whitelists
- TTL-based caching for introspection results
- Freqtrade version validation at startup
- Structured JSON logging to stderr
- Comprehensive test suite
- CI/CD with GitHub Actions
- Security documentation with MCP threat model

[Unreleased]: https://github.com/yalcin/freqtrade-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/yalcin/freqtrade-mcp/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/yalcin/freqtrade-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/yalcin/freqtrade-mcp/releases/tag/v0.1.0
