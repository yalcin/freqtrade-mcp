"""Startup validation of the installed freqtrade version."""

import importlib
import logging
from importlib.metadata import PackageNotFoundError, version

from packaging.version import InvalidVersion, Version

from freqtrade_mcp.constants import ISTRATEGY_CLASS_PATH, MIN_FREQTRADE_VERSION
from freqtrade_mcp.exceptions import VersionError

logger = logging.getLogger(__name__)


def _parse_version(version_str: str) -> Version | None:
    """Parse a version string using PEP 440 semantics.

    Replaces a hand-rolled numeric-prefix parser that mapped "2026.2rc1" onto
    (2026, 2) — making a release candidate compare equal to the final release
    — and silently dropped anything it did not understand.

    Args:
        version_str: Version string such as "2026.6" or "2026.7.dev0".

    Returns:
        The parsed version, or None if it is not PEP 440 compliant.
    """
    try:
        return Version(version_str)
    except InvalidVersion:
        return None


def check_freqtrade_version() -> str:
    """Validate that freqtrade is installed and meets the minimum version.

    Returns:
        The installed freqtrade version string.

    Raises:
        VersionError: If freqtrade is not installed or version is too old.
    """
    try:
        installed_version = version("freqtrade")
    except PackageNotFoundError as exc:
        msg = (
            "freqtrade is not installed. "
            f"Please install freqtrade >= {MIN_FREQTRADE_VERSION} to use freqtrade-mcp."
        )
        raise VersionError(msg) from exc

    installed = _parse_version(installed_version)
    if installed is None:
        # An unparseable version is not grounds for refusing to start: it is
        # usually a local or vendored build. Warn and continue.
        logger.warning(
            "Cannot parse freqtrade version %r; skipping the minimum version check.",
            installed_version,
        )
        return installed_version

    if installed < Version(MIN_FREQTRADE_VERSION):
        msg = (
            f"freqtrade {installed_version} is installed, "
            f"but freqtrade-mcp requires >= {MIN_FREQTRADE_VERSION}. "
            "Please upgrade freqtrade."
        )
        raise VersionError(msg)

    logger.info("freqtrade %s detected (minimum: %s)", installed_version, MIN_FREQTRADE_VERSION)
    return installed_version


def check_freqtrade_importable() -> None:
    """Verify that the freqtrade strategy interface can actually be imported.

    ``check_freqtrade_version`` only reads distribution metadata, which stays
    valid even when the package cannot be imported. Callers get a diagnostic
    up front instead of discovering the problem on every introspection call.

    This is expected to fail on a stock install: freqtrade declares scipy only
    under its ``hyperopt`` extra, while ``freqtrade.data.metrics`` imports it
    unconditionally and sits on the import path of the strategy interface.
    Treat the failure as a warning, not as a reason to refuse service — see
    :func:`freqtrade_mcp.server._validate_freqtrade_installation`.

    Raises:
        VersionError: If the freqtrade strategy interface cannot be imported.
    """
    module_path = ISTRATEGY_CLASS_PATH.rsplit(".", maxsplit=1)[0]
    try:
        importlib.import_module(module_path)
    except (Exception, SystemExit) as exc:
        # SystemExit is included deliberately: freqtrade.plot.plotting calls
        # exit(1) at import time when plotly is missing. Being a BaseException
        # it would escape both this handler and main()'s, killing the server
        # with no diagnostic instead of degrading to a warning.
        # KeyboardInterrupt is deliberately not caught.
        reason = type(exc).__name__
        if isinstance(exc, ModuleNotFoundError) and exc.name:
            reason = f"{reason}: missing dependency {exc.name!r}"

        msg = (
            f"freqtrade is installed but '{module_path}' cannot be imported "
            f"({reason}). This usually means an optional "
            "freqtrade dependency is absent — scipy in particular is only "
            "installed by the 'hyperopt' extra. Install it in the same "
            "environment as freqtrade-mcp, e.g. 'pip install freqtrade[hyperopt]'."
        )
        raise VersionError(msg) from None

    logger.info("freqtrade strategy interface imported successfully")
