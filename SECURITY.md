# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in freqtrade-mcp, please report it responsibly:

1. **Do NOT** create a public GitHub issue
2. Email: yalcin@webliyacelebi.com
3. Include a description of the vulnerability, steps to reproduce, and potential impact

We will respond as soon as possible.

## MCP Threat Model

freqtrade-mcp is designed to be resistant to common MCP attack vectors:

### Prompt Injection via Tool Descriptions

- All tool descriptions are **hardcoded static strings**
- Tool descriptions never include user/LLM-generated content
- No dynamic content is injected into tool metadata

### Tool Poisoning

- All tool metadata is defined in source code, not loaded from external sources
- Tool annotations (`readOnlyHint`, `destructiveHint`, etc.) are hardcoded
- No external configuration can modify tool behavior

### Path Traversal

- Module paths are validated against `^freqtrade(\.[A-Za-z_][A-Za-z0-9_]*)+$`
- Documentation topic names are validated against `^[a-zA-Z0-9][a-zA-Z0-9_-]*(/[a-zA-Z0-9][a-zA-Z0-9_-]*)*$`
- Documentation file paths are verified to be under the configured docs root via `Path.relative_to()`
- Only `freqtrade.*` namespace is accessible for code introspection
- No arbitrary file reads or writes

### Information Leakage

- Only exposes freqtrade's public API (no private/dunder methods)
- Does not expose system internals, environment variables, or filesystem structure
- Logging never includes sensitive data
- Error messages are sanitized

### Code Injection

- **No `eval()` or `exec()`** anywhere in the codebase
- Uses only `inspect` and `ast` modules for introspection
- All inputs are validated with strict allow-lists and length limits before use
- Search accepts only glob-style patterns; literals are escaped before compiling,
  so callers cannot inject regular-expression operators or trigger ReDoS

### Transport Security

- Uses **stdio transport only** (local process communication)
- No network listeners, no HTTP endpoints
- No remote connections

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Security Best Practices for Users

1. Only install freqtrade-mcp-server from trusted sources (PyPI, GitHub)
2. Keep freqtrade and freqtrade-mcp-server updated to the latest versions
3. Review the MCP client configuration to ensure only intended tools are exposed
4. Set `FREQTRADE_MCP_LOG_LEVEL=WARNING` or higher in production
