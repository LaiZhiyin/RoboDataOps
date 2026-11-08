"""Errors that can be presented directly to an operator."""


class RoboDataOpsError(Exception):
    """Base class for an actionable domain error."""


class ValidationError(RoboDataOpsError):
    """An input violates the declared data or planning contract."""


class DataSourceError(RoboDataOpsError):
    """A source cannot be read or its format is unsupported."""
