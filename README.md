# freqtrade-mcp

> I designed and built this project for my own use. All architectural decisions, tool design, and the security model are my own work. I used Claude Opus as a coding assistant during the development process. This is a research and personal-use project.

A **read-only MCP (Model Context Protocol) server** that provides LLM tools with introspection data about the [Freqtrade](https://www.freqtrade.io/) codebase. Helps LLMs write faster, more reliable Freqtrade strategy code by giving them access to overridable functions, classes, variables, docstrings, type hints, and method signatures from the live Freqtrade installation.

## Disclaimer

**This is a research and personal-use project.** It provides read-only introspection of the Freqtrade codebase to assist LLM-based code generation. It does **NOT** execute trades, access exchange APIs, or manage funds. It is **NOT** financial advice software.

The author(s) accept **NO responsibility or liability** for any direct, indirect, incidental, or consequential damages arising from the use of this software, including but not limited to financial losses from trading strategies developed with its assistance. Use entirely at your own risk. Always backtest thoroughly before deploying any strategy with real capital.

## Usage Philosophy

`freqtrade-mcp` is not meant to replace reading the Freqtrade documentation.

It is a read-only reference layer for LLM agents. The goal is to help agents check the actual docs, public strategy APIs, method signatures, config keys, enums, and DataFrame column references before suggesting code.

Agents should prefer documented public APIs and avoid relying on undocumented Freqtrade internals in strategy code.

## Features

- **Strategy Method Introspection**: List and inspect all overridable IStrategy methods with full signatures, type hints, and docstrings
- **Class Inspection**: Explore any freqtrade class — MRO, attributes, public methods
- **Enum Discovery**: List and inspect all trading-related enums and their values
- **Codebase Search**: Search for classes, functions, constants, and enums by name pattern
- **Callback Details**: Get detailed info about strategy callbacks (bot_start, custom_stoploss, etc.)
- **Config Schema**: Browse the installed freqtrade schema and its descriptions
- **DataFrame Columns**: Discover available DataFrame columns in strategy methods
- **Documentation Access**: Browse, search, and read freqtrade markdown documentation
- **Version Info**: Check installed freqtrade and MCP server versions

## Security

- **Read-only**: No trading, no exchange connections, no side effects
- **Input validation**: All LLM inputs use strict allow-lists and length limits;
  code search accepts only glob-style patterns built from escaped literals
- **No eval/exec**: Only uses Python's `inspect` and `ast` modules
- **No import side effects in search**: symbol search parses source with `ast`
  rather than importing it, so no third-party module-level code runs
- **Namespace restricted**: Only inspects `freqtrade.*` modules
- **stdio transport**: Local-only, no network exposure

## Requirements

- Python >= 3.13
- freqtrade >= 2026.2
- mcp[cli] >= 1.26.0

## Installation

```bash
pip install freqtrade-mcp-server
```

> **Important:** Install `freqtrade-mcp-server` into the **same environment** as the
> freqtrade version you develop against, so introspection reflects the code you
> actually run. Avoid isolated installs (pipx/uvx): they pull in their own copy of
> freqtrade, and the server would inspect that copy instead of yours.

Or install from source:

```bash
git clone https://github.com/yalcin/freqtrade-mcp.git
cd freqtrade-mcp
pip install -e ".[dev]"
```

## Usage

### Claude Code (CLI)

```bash
claude mcp add freqtrade-mcp \
  -e FREQTRADE_DOCS_PATH=/path/to/freqtrade/docs \
  -- "$(command -v freqtrade-mcp)"
```

### Claude Desktop (macOS / Windows only)

> **Note:** Claude Desktop is not available on Linux. This configuration is based on official documentation but has **not been tested** by the author. If you encounter issues or have corrections, pull requests are welcome.

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "freqtrade": {
      "command": "freqtrade-mcp",
      "args": [],
      "env": {
        "FREQTRADE_MCP_LOG_LEVEL": "INFO",
        "FREQTRADE_DOCS_PATH": "/path/to/freqtrade/docs"
      }
    }
  }
}
```

### OpenAI Codex CLI

Codex CLI is a terminal-based tool that runs on all platforms including Linux.

Add to your `~/.codex/config.toml` (or project-scoped `.codex/config.toml`):

```toml
[mcp_servers.freqtrade]
command = "freqtrade-mcp"
args = []

[mcp_servers.freqtrade.env]
FREQTRADE_MCP_LOG_LEVEL = "INFO"
FREQTRADE_DOCS_PATH = "/path/to/freqtrade/docs"
```

Or via CLI:

```bash
codex mcp add freqtrade-mcp \
  --env FREQTRADE_DOCS_PATH="<FREQTRADE_DOCS_PATH>" \
  -- "$(command -v freqtrade-mcp)"
```

### Codex Desktop App (macOS only)

> **Note:** The Codex desktop app is currently macOS-only (Apple Silicon). Windows and Linux versions are not yet available. This configuration is based on official documentation but has **not been tested** by the author. If you encounter issues or have corrections, pull requests are welcome.

The Codex desktop app shares the same `~/.codex/config.toml` configuration file with the CLI. Use the config shown in the [Codex CLI](#openai-codex-cli) section above — it applies to both.

### Codex IDE Extension (VS Code / Cursor / Windsurf)

> **Note:** Available on macOS and Linux. Windows support is experimental (WSL recommended).

The Codex IDE extension also shares `~/.codex/config.toml` with the CLI and desktop app. Use the same configuration shown in the [Codex CLI](#openai-codex-cli) section. In the extension, you can access MCP settings via the gear menu.

> **Integrations note:** Claude Code (CLI) and Codex CLI configurations have been tested and verified. Claude Desktop, Codex desktop app, and Codex IDE extension configurations are based on official documentation but have **not been tested** by the author. If you encounter issues or have corrections, pull requests are welcome.

### Generic stdio

```bash
FREQTRADE_DOCS_PATH=/path/to/freqtrade/docs freqtrade-mcp
```

## Available Tools

| Tool | Description |
|------|-------------|
| `freqtrade_list_strategy_methods` | List all overridable IStrategy methods |
| `freqtrade_get_method_signature` | Get full signature of a specific method |
| `freqtrade_get_class_info` | Inspect any freqtrade class |
| `freqtrade_list_enums` | List trading-related enums |
| `freqtrade_get_enum_values` | Get values of a specific enum |
| `freqtrade_search_codebase` | Search for symbols by name pattern (statically indexed, no imports) |
| `freqtrade_get_callback_info` | Get detailed callback method info |
| `freqtrade_get_config_schema` | Browse configuration keys |
| `freqtrade_get_dataframe_columns` | List DataFrame columns in strategy methods |
| `freqtrade_get_version_info` | Get version information |
| `freqtrade_list_docs` | List available documentation topics |
| `freqtrade_search_docs` | Full-text search across all documentation |
| `freqtrade_get_doc` | Read a documentation page, or one section of it |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FREQTRADE_DOCS_PATH` | *(not set)* | Path to the freqtrade `docs/` directory for documentation tools |
| `FREQTRADE_MCP_LOG_LEVEL` | `WARNING` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

### Documentation Tools

To enable documentation tools, set `FREQTRADE_DOCS_PATH` to the `docs/` directory of a cloned freqtrade repository:

```bash
export FREQTRADE_DOCS_PATH=/path/to/freqtrade/docs
```

If not set, the server starts normally but documentation tools will return a guidance message instead of content. The documentation is cached with a 1-hour TTL and refreshes automatically.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run only the smoke tests against a real freqtrade installation
# (skipped automatically when freqtrade is not importable)
pytest -m integration

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/
```

## License

[GPLv3](LICENSE)
