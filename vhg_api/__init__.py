"""Public package interface for vhg_api."""

from .auth import (
    SecurityPayload,
    build_security_payload,
    calculate_challenge_password,
    make_challenge,
)
from .client import AccessRights, TDSClient, build_api_url
from .download import DownloadResult, download_configured, select_sources
from .runner import RunSummary, SourceRunResult, run_download
from .storage import RAW_COLUMNS, incremental_start, normalize_raw_frame, read_raw_archive, update_raw_archive
from .config import (
    ApiConfig,
    AppConfig,
    ConfigError,
    IncrementalConfig,
    MeasurementSource,
    ProxyConfig,
    Station,
    StorageConfig,
    load_config,
)
from .errors import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    DownloadError,
    VHGAPIError,
)

__all__ = [
    "APIError",
    "AccessRights",
    "ApiConfig",
    "AppConfig",
    "AuthenticationError",
    "ConfigError",
    "ConfigurationError",
    "ConnectionError",
    "DownloadError",
    "DownloadResult",
    "IncrementalConfig",
    "MeasurementSource",
    "ProxyConfig",
    "RAW_COLUMNS",
    "RunSummary",
    "SourceRunResult",
    "SecurityPayload",
    "Station",
    "StorageConfig",
    "TDSClient",
    "VHGAPIError",
    "build_api_url",
    "build_security_payload",
    "calculate_challenge_password",
    "download_configured",
    "incremental_start",
    "load_config",
    "make_challenge",
    "normalize_raw_frame",
    "read_raw_archive",
    "select_sources",
    "run_download",
    "update_raw_archive",
]

__version__ = "1.0.0"
