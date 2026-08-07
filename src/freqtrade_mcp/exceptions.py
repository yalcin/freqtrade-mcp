"""Custom exception hierarchy for freqtrade-mcp."""


class FreqtradeMCPError(Exception):
    """Base exception for all freqtrade-mcp errors."""


class VersionError(FreqtradeMCPError):
    """Raised when freqtrade version is incompatible or not installed."""


class ValidationError(FreqtradeMCPError):
    """Raised when input validation fails."""


class IntrospectionError(FreqtradeMCPError):
    """Raised when introspection of a freqtrade module or class fails."""


class ModuleImportError(IntrospectionError):
    """Raised when a requested freqtrade module cannot be imported."""


class ClassNotFoundError(IntrospectionError):
    """Raised when a requested class is not found in a module."""


class MethodNotFoundError(IntrospectionError):
    """Raised when a requested method is not found on a class."""


class DocTopicNotFoundError(FreqtradeMCPError):
    """Raised when a requested documentation topic does not exist."""


class DocSectionNotFoundError(FreqtradeMCPError):
    """Raised when a requested section does not exist in a documentation page."""
