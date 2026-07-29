"""Exceptions raised by :mod:`vhg_api`."""

from __future__ import annotations


class VHGAPIError(Exception):
    """Base class for all package-specific errors."""


class ConfigurationError(VHGAPIError, ValueError):
    """Raised when configuration is missing, malformed, or inconsistent."""


class AuthenticationError(VHGAPIError):
    """Raised when credentials are rejected or authentication cannot be prepared."""


class ConnectionError(VHGAPIError):
    """Raised when the TDS server cannot be reached reliably."""


class APIError(VHGAPIError):
    """Raised when TDS returns an invalid or unsuccessful response."""


class DownloadError(VHGAPIError):
    """Raised when a data download cannot be completed or stored."""
