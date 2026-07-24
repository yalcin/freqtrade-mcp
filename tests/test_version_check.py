"""Tests for freqtrade version checking."""

from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

import pytest
from packaging.version import Version

from freqtrade_mcp._version_check import (
    _parse_version,
    check_freqtrade_importable,
    check_freqtrade_version,
)
from freqtrade_mcp.exceptions import VersionError


class TestParseVersion:
    """Tests for _parse_version."""

    def test_simple_version(self) -> None:
        """Simple version strings should parse correctly."""
        assert _parse_version("2026.6") == Version("2026.6")

    def test_three_part_version(self) -> None:
        """Three-part version strings should parse correctly."""
        assert _parse_version("2026.2.1") == Version("2026.2.1")

    def test_prerelease_sorts_below_final(self) -> None:
        """A release candidate must compare below its final release.

        The previous hand-rolled parser mapped "2026.2rc1" onto (2026, 2),
        making the RC compare equal to the final release.
        """
        rc = _parse_version("2026.2rc1")
        assert rc is not None
        assert rc < Version("2026.2")

    def test_dev_version(self) -> None:
        """Dev builds are ordered correctly against releases."""
        dev = _parse_version("2026.7.dev1")
        assert dev is not None
        assert Version("2026.6") < dev < Version("2026.7")

    def test_invalid_version_returns_none(self) -> None:
        """Non-PEP440 strings are reported rather than silently mangled."""
        assert _parse_version("not-a-version") is None


class TestCheckFreqtradeVersion:
    """Tests for check_freqtrade_version."""

    def test_not_installed(self) -> None:
        """Should raise VersionError when freqtrade is not installed."""
        with (
            patch(
                "freqtrade_mcp._version_check.version",
                side_effect=PackageNotFoundError("freqtrade"),
            ),
            pytest.raises(VersionError, match="not installed"),
        ):
            check_freqtrade_version()

    def test_version_too_old(self) -> None:
        """Should raise VersionError when version is below minimum."""
        with (
            patch("freqtrade_mcp._version_check.version", return_value="2025.1"),
            pytest.raises(VersionError, match="requires >="),
        ):
            check_freqtrade_version()

    def test_exact_minimum_version(self) -> None:
        """Should accept the exact minimum version."""
        with patch("freqtrade_mcp._version_check.version", return_value="2026.2"):
            result = check_freqtrade_version()
            assert result == "2026.2"

    def test_newer_version(self) -> None:
        """Should accept newer versions."""
        with patch("freqtrade_mcp._version_check.version", return_value="2026.6"):
            result = check_freqtrade_version()
            assert result == "2026.6"

    def test_prerelease_below_minimum_is_rejected(self) -> None:
        """A release candidate of the minimum version is not the release."""
        with (
            patch("freqtrade_mcp._version_check.version", return_value="2026.2rc1"),
            pytest.raises(VersionError, match="requires >="),
        ):
            check_freqtrade_version()

    def test_unparseable_version_is_accepted_with_a_warning(self) -> None:
        """A local or vendored build should not block startup."""
        with patch("freqtrade_mcp._version_check.version", return_value="custom-build"):
            assert check_freqtrade_version() == "custom-build"


class TestCheckFreqtradeImportable:
    """Tests for check_freqtrade_importable."""

    def test_passes_when_importable(self) -> None:
        """Should not raise when the strategy interface imports cleanly."""
        with patch("freqtrade_mcp._version_check.importlib.import_module") as mock_import:
            check_freqtrade_importable()
            mock_import.assert_called_once_with("freqtrade.strategy.interface")

    def test_raises_on_missing_transitive_dependency(self) -> None:
        """An incomplete install must fail at startup, not on every tool call.

        Distribution metadata stays valid when a transitive dependency is
        missing, so check_freqtrade_version alone reports success while every
        introspection call fails later with ModuleImportError.
        """
        with (
            patch(
                "freqtrade_mcp._version_check.importlib.import_module",
                side_effect=ModuleNotFoundError("No module named 'scipy'"),
            ),
            pytest.raises(VersionError, match="cannot be imported"),
        ):
            check_freqtrade_importable()

    def test_raises_on_non_import_error(self) -> None:
        """Any exception from the import, not just ImportError, must be caught."""
        with (
            patch(
                "freqtrade_mcp._version_check.importlib.import_module",
                side_effect=RuntimeError("broken top-level code"),
            ),
            pytest.raises(VersionError, match="RuntimeError"),
        ):
            check_freqtrade_importable()
