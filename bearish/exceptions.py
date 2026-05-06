"""Domain-specific exceptions."""


class BearishError(Exception):
    """Base class for all bearish errors."""


class SourceError(BearishError):
    """Raised when a data source fails to deliver data."""


class RepositoryError(BearishError):
    """Raised when the repository cannot read or write data."""
