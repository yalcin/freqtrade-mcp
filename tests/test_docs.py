"""Tests for the documentation reader module."""

from pathlib import Path

import pytest

from freqtrade_mcp.docs import (
    _discover_docs_path,
    _extract_title,
    _load_docs_index,
    _scan_directory,
    get_doc,
    list_docs,
    search_docs,
)
from freqtrade_mcp.exceptions import (
    DocSectionNotFoundError,
    DocTopicNotFoundError,
    ValidationError,
)
from freqtrade_mcp.validators import validate_doc_search_query, validate_doc_topic


class TestDiscoverDocsPath:
    """Tests for _discover_docs_path."""

    def test_env_var_valid_path(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = _discover_docs_path()
        assert result is not None
        assert result == fake_docs_dir.resolve()

    def test_env_var_invalid_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(empty_dir))
        result = _discover_docs_path()
        assert result is None
        assert str(empty_dir) not in caplog.text

    def test_env_var_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        result = _discover_docs_path()
        assert result is None

    def test_env_var_nonexistent_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", "/nonexistent/path")
        result = _discover_docs_path()
        assert result is None


class TestExtractTitle:
    """Tests for _extract_title."""

    def test_h1_title(self) -> None:
        content = "# My Great Title\n\nSome content here."
        assert _extract_title(content, "test.md") == "My Great Title"

    def test_h1_after_other_lines(self) -> None:
        content = "![image](logo.png)\n\n# Actual Title\n\nContent."
        assert _extract_title(content, "test.md") == "Actual Title"

    def test_fallback_to_filename(self) -> None:
        content = "No headings here, just plain text."
        assert _extract_title(content, "strategy-callbacks.md") == "Strategy Callbacks"

    def test_ignores_h2(self) -> None:
        content = "## This is H2\n\nNot H1."
        assert _extract_title(content, "some-file.md") == "Some File"

    def test_empty_content(self) -> None:
        assert _extract_title("", "fallback-name.md") == "Fallback Name"


class TestLoadDocsIndex:
    """Tests for _load_docs_index."""

    def test_loads_toplevel_files(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        index = _load_docs_index()
        assert index is not None
        assert "strategy-callbacks" in index
        assert "configuration" in index
        assert "backtesting" in index

    def test_loads_commands_subdir(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        index = _load_docs_index()
        assert index is not None
        assert "commands/backtesting" in index
        assert "commands/trade" in index

    def test_returns_none_when_no_docs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        index = _load_docs_index()
        assert index is None

    def test_index_values_structure(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        index = _load_docs_index()
        assert index is not None
        title, content, size = index["strategy-callbacks"]
        assert title == "Strategy Callbacks"
        assert "custom_stoploss" in content
        assert size > 0

    def test_read_failure_does_not_expose_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Read errors may identify a topic, but never its absolute path or raw error."""
        doc_file = tmp_path / "private-notes.md"
        doc_file.write_text("# Private notes")

        def fail_read_text(_path: Path, *, encoding: str) -> str:
            del encoding
            raise OSError(f"cannot read {doc_file}")

        monkeypatch.setattr(Path, "read_text", fail_read_text)
        assert _scan_directory(tmp_path, tmp_path) == {}
        assert "private-notes" in caplog.text
        assert str(tmp_path) not in caplog.text
        assert "cannot read" not in caplog.text


class TestListDocs:
    """Tests for list_docs."""

    def test_lists_all_topics(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = list_docs()
        assert result is not None
        assert len(result) == 5
        topics = [t.topic for t in result]
        assert "strategy-callbacks" in topics
        assert "commands/backtesting" in topics

    def test_filter_by_keyword(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = list_docs(filter_str="strategy")
        assert result is not None
        assert len(result) >= 1
        assert all("strategy" in t.topic.lower() or "strategy" in t.title.lower() for t in result)

    def test_filter_with_hyphen(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = list_docs(filter_str="strategy-callbacks")
        assert result is not None
        assert [t.topic for t in result] == ["strategy-callbacks"]

    def test_returns_none_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        result = list_docs()
        assert result is None

    def test_topic_has_correct_path(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = list_docs()
        assert result is not None
        cb_topic = next(t for t in result if t.topic == "strategy-callbacks")
        assert cb_topic.path == "strategy-callbacks.md"
        cmd_topic = next(t for t in result if t.topic == "commands/backtesting")
        assert cmd_topic.path == "commands/backtesting.md"


class TestSearchDocs:
    """Tests for search_docs."""

    def test_single_word_search(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = search_docs("stoploss")
        assert result is not None
        assert len(result) >= 1
        assert any("stoploss" in r.snippet.lower() for r in result)

    def test_multi_word_and_search(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = search_docs("custom stoploss")
        assert result is not None
        assert len(result) >= 1
        # All results must be from docs containing both words
        for r in result:
            assert r.topic == "strategy-callbacks"

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = search_docs("BACKTESTING")
        assert result is not None
        assert len(result) >= 1

    def test_no_results(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = search_docs("xyznonexistent")
        assert result is not None
        assert len(result) == 0

    def test_max_results_limit(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = search_docs("the", max_results=2)
        assert result is not None
        assert len(result) <= 2

    def test_returns_none_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        result = search_docs("anything")
        assert result is None

    def test_snippet_includes_context(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = search_docs("bot_start")
        assert result is not None
        assert len(result) >= 1
        # Snippet should have multiple lines (context around the match)
        assert "\n" in result[0].snippet

    def test_line_number_is_positive(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = search_docs("Callbacks")
        assert result is not None
        for r in result:
            assert r.line_number >= 1


class TestGetDoc:
    """Tests for get_doc."""

    def test_valid_topic(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("strategy-callbacks")
        assert result is not None
        assert result.topic == "strategy-callbacks"
        assert result.title == "Strategy Callbacks"
        assert "custom_stoploss" in result.content
        assert result.size_bytes > 0

    def test_commands_subtopic(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("commands/backtesting")
        assert result is not None
        assert result.topic == "commands/backtesting"
        assert "freqtrade backtesting" in result.content

    def test_topic_not_found(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        with pytest.raises(DocTopicNotFoundError, match="not found"):
            get_doc("nonexistent-topic")

    def test_returns_none_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FREQTRADE_DOCS_PATH", raising=False)
        result = get_doc("strategy-callbacks")
        assert result is None

    def test_suggests_close_matches(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        # "strategy" is a substring of "strategy-callbacks", so suggestion should appear
        with pytest.raises(DocTopicNotFoundError, match="Did you mean"):
            get_doc("strategy-callback")
        # "backtest" is a substring of "backtesting"
        with pytest.raises(DocTopicNotFoundError, match="Did you mean"):
            get_doc("backtest")


class TestGetDocSections:
    """Tests for section extraction in get_doc."""

    def test_lists_sections(self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path) -> None:
        """The '##' headings are always advertised, so a caller can navigate."""
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("strategy-callbacks")
        assert result is not None
        assert result.sections == ["bot_start", "custom_stoploss"]

    def test_returns_only_the_requested_section(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        """A section request excludes the rest of the page."""
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("strategy-callbacks", section="bot_start")
        assert result is not None
        assert result.section == "bot_start"
        assert result.content.startswith("## bot_start")
        assert "Called once at startup." in result.content
        assert "custom_stoploss" not in result.content

    def test_section_match_is_case_insensitive(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("strategy-callbacks", section="BOT_START")
        assert result is not None
        assert result.content.startswith("## bot_start")

    def test_last_section_runs_to_end_of_page(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("strategy-callbacks", section="custom_stoploss")
        assert result is not None
        assert "Calculate custom stoploss." in result.content

    def test_empty_section_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        """An empty section must not silently mean "the whole page".

        A truthiness check let "" through unvalidated while rejecting "   ",
        so the same intent produced two different behaviours.
        """
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        with pytest.raises(ValidationError):
            get_doc("strategy-callbacks", section="")
        with pytest.raises(ValidationError):
            get_doc("strategy-callbacks", section="   ")

    def test_unknown_section_lists_the_valid_ones(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        """The error must tell the caller what it could have asked for."""
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        with pytest.raises(DocSectionNotFoundError, match="bot_start"):
            get_doc("strategy-callbacks", section="does-not-exist")


class TestGetDocPagination:
    """Tests for slicing in get_doc."""

    def test_short_page_is_not_truncated(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("backtesting")
        assert result is not None
        assert result.truncated is False
        assert result.next_offset is None
        assert result.offset == 0
        assert result.returned_chars == result.total_chars

    def test_truncates_and_reports_next_offset(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        first = get_doc("strategy-callbacks", max_chars=30)
        assert first is not None
        assert first.truncated is True
        assert first.next_offset == first.returned_chars
        assert first.returned_chars < first.total_chars

    def test_following_next_offset_reads_the_whole_page(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        """Walking next_offset must reconstruct the page without gaps."""
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        full = get_doc("strategy-callbacks")
        assert full is not None

        collected = ""
        offset: int | None = 0
        while offset is not None:
            page = get_doc("strategy-callbacks", offset=offset, max_chars=30)
            assert page is not None
            collected += page.content
            offset = page.next_offset

        assert collected == full.content

    def test_offset_past_end_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        result = get_doc("strategy-callbacks", offset=100_000)
        assert result is not None
        assert result.content == ""
        assert result.truncated is False
        assert result.next_offset is None

    def test_section_scope_is_paginated(
        self, monkeypatch: pytest.MonkeyPatch, fake_docs_dir: Path
    ) -> None:
        """total_chars reflects the section, not the whole page."""
        monkeypatch.setenv("FREQTRADE_DOCS_PATH", str(fake_docs_dir))
        page = get_doc("strategy-callbacks")
        section = get_doc("strategy-callbacks", section="bot_start")
        assert page is not None
        assert section is not None
        assert section.total_chars < page.total_chars


class TestValidateDocTopic:
    """Tests for validate_doc_topic."""

    def test_valid_topics(self) -> None:
        assert validate_doc_topic("strategy-callbacks") == "strategy-callbacks"
        assert validate_doc_topic("configuration") == "configuration"
        assert validate_doc_topic("commands/backtesting") == "commands/backtesting"
        assert validate_doc_topic("freqai-running") == "freqai-running"

    def test_path_traversal_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_doc_topic("../etc/passwd")
        with pytest.raises(ValidationError):
            validate_doc_topic("../../secret")

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_doc_topic("/etc/passwd")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_doc_topic("")

    def test_special_chars_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_doc_topic("foo;rm -rf")
        with pytest.raises(ValidationError):
            validate_doc_topic("foo bar")
        with pytest.raises(ValidationError):
            validate_doc_topic("foo..bar")


class TestValidateDocSearchQuery:
    """Tests for validate_doc_search_query."""

    def test_valid_query(self) -> None:
        assert validate_doc_search_query("custom stoploss") == "custom stoploss"
        assert validate_doc_search_query("  trimmed  ") == "trimmed"

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_doc_search_query("")
        with pytest.raises(ValidationError):
            validate_doc_search_query("   ")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            validate_doc_search_query("a" * 300)
