"""HTTP client for the Tetraedre TDS JSON API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urljoin

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import build_security_payload
from .config import AppConfig
from .errors import APIError, AuthenticationError, ConnectionError


@dataclass(frozen=True)
class AccessRights:
    """Normalized response from the ``check_access`` operation."""

    access_granted: bool
    view: bool
    manage: bool
    import_data: bool
    export_data: bool
    equipment: Any = None

    @classmethod
    def from_response(cls, response: Mapping[str, Any]) -> "AccessRights":
        """Build normalized access rights from a raw API response mapping."""
        return cls(
            access_granted=_api_bool(response.get("access_granted")),
            view=_api_bool(response.get("view")),
            manage=_api_bool(response.get("manage")),
            import_data=_api_bool(response.get("import_data")),
            export_data=_api_bool(response.get("export_data")),
            equipment=response.get("equipment"),
        )


def _api_bool(value: Any) -> bool:
    """Convert the boolean encodings used by TDS into Python ``bool``."""
    if value in (True, 1, "1"):
        return True
    if value in (False, 0, "0", None, ""):
        return False
    raise APIError(f"Unexpected boolean value returned by TDS: {value!r}")


def build_api_url(server: str, endpoint: str) -> str:
    """Join a server and endpoint without losing a server subpath."""
    base = server.strip()
    page = endpoint.strip()
    if not base:
        raise APIError("API server may not be empty")
    if not page:
        raise APIError("API endpoint may not be empty")
    if not base.lower().startswith(("http://", "https://")):
        base = f"https://{base}"
    return urljoin(f"{base.rstrip('/')}/", page.lstrip("/"))


def _to_unix_timestamp(value: str | datetime | pd.Timestamp, *, name: str) -> int:
    """Convert a datetime-like value to a UTC UNIX timestamp."""
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not a valid datetime: {value!r}") from exc
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return int(timestamp.timestamp())


class TDSClient:
    """Reusable, configuration-driven client for TDS JSON operations."""

    def __init__(
        self,
        config: AppConfig,
        *,
        session: requests.Session | None = None,
        retry_total: int = 3,
        retry_backoff_factor: float = 0.5,
    ) -> None:
        """Create a reusable client and configure its HTTP session."""
        self.config = config
        self.url = build_api_url(config.api.server, config.api.endpoint)
        self.session = session or requests.Session()
        self._owns_session = session is None
        self._configure_session(retry_total, retry_backoff_factor)

    def _configure_session(self, retry_total: int, retry_backoff_factor: float) -> None:
        """Apply headers, proxy policy, and POST retry behaviour."""
        self.session.headers.update({"Accept": "application/json"})
        self.session.trust_env = False
        if self.config.proxy.enabled:
            proxies: dict[str, str] = {}
            if self.config.proxy.http:
                proxies["http"] = self.config.proxy.http
            if self.config.proxy.https:
                proxies["https"] = self.config.proxy.https
            self.session.proxies.update(proxies)

        if retry_total < 0:
            raise ValueError("retry_total must be non-negative")
        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            status=retry_total,
            backoff_factor=retry_backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"POST"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def close(self) -> None:
        """Close the underlying session when owned by this client."""
        if self._owns_session:
            self.session.close()

    def __enter__(self) -> "TDSClient":
        """Return this client for use as a context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close an internally owned session when leaving the context."""
        self.close()

    def request(
        self,
        operation: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        authenticated: bool = True,
    ) -> Any:
        """Send one JSON operation and return the decoded JSON value."""
        operation_name = operation.strip()
        if not operation_name:
            raise APIError("Operation may not be empty")

        payload: dict[str, Any] = {"operation": operation_name}
        if authenticated:
            payload.update(build_security_payload(self.config.api).as_dict())
        if parameters:
            protected = {"operation", "username", "dossier_id", "challenge", "challenge_password"}
            overlap = protected.intersection(parameters)
            if overlap:
                raise APIError(
                    "Operation parameters may not override protected field(s): "
                    + ", ".join(sorted(overlap))
                )
            payload.update(parameters)

        try:
            response = self.session.post(
                self.url,
                json=payload,
                timeout=self.config.api.timeout_seconds,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise ConnectionError(
                f"TDS request timed out after {self.config.api.timeout_seconds} seconds"
            ) from exc
        except requests.RequestException as exc:
            raise ConnectionError(f"Unable to reach TDS at {self.url}: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            preview = response.text[:200].replace("\n", " ")
            raise APIError(f"TDS returned invalid JSON: {preview!r}") from exc

        if isinstance(data, Mapping):
            self._raise_for_api_error(data, operation_name)
        return data

    @staticmethod
    def _raise_for_api_error(data: Mapping[str, Any], operation: str) -> None:
        """Translate API-level error fields into typed package exceptions."""
        error_value = data.get("error") or data.get("error_message")
        if error_value:
            message = str(error_value)
            if any(token in message.lower() for token in ("password", "challenge", "access", "auth")):
                raise AuthenticationError(message)
            raise APIError(f"TDS operation {operation!r} failed: {message}")

    def ping(self) -> bool:
        """Return ``True`` only when TDS answers ``{'ping': 'pong'}``."""
        data = self.request("ping", authenticated=False)
        if not isinstance(data, Mapping) or data.get("ping") != "pong":
            raise APIError(f"Unexpected ping response: {data!r}")
        return True

    def check_access(self) -> AccessRights:
        """Return the current user's access rights for the configured dossier."""
        data = self.request("check_access")
        if not isinstance(data, Mapping):
            raise APIError(f"Unexpected check_access response: {data!r}")
        rights = AccessRights.from_response(data)
        if not rights.access_granted:
            raise AuthenticationError(
                "TDS did not grant access for the configured username and dossier_id"
            )
        return rights

    def get_values(
        self,
        *,
        measurement_set: str | None = None,
        measurement_set_id: int | None = None,
        media: int,
        start: str | datetime | pd.Timestamp,
        end: str | datetime | pd.Timestamp,
        limit: int = 0,
        sort: str = "ASC",
        response_format: int = 0,
    ) -> pd.DataFrame:
        """Retrieve one TDS series and return normalized UTC data.

        Exactly one of ``measurement_set`` (the TDS metering code) and
        ``measurement_set_id`` must be supplied. Naive datetimes are interpreted
        as UTC. Both boundaries are inclusive, matching the TDS API.
        """
        if (measurement_set is None) == (measurement_set_id is None):
            raise ValueError(
                "Provide exactly one of measurement_set or measurement_set_id"
            )
        try:
            media_number = int(media)
            limit_number = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("media and limit must be integers") from exc
        if media_number < 0 or limit_number < 0:
            raise ValueError("media and limit must be non-negative")

        sort_value = sort.upper().strip()
        if sort_value not in {"ASC", "DESC"}:
            raise ValueError("sort must be 'ASC' or 'DESC'")
        if response_format not in {0, 1}:
            raise ValueError("response_format must be 0 or 1")

        t0 = _to_unix_timestamp(start, name="start")
        t1 = _to_unix_timestamp(end, name="end")
        if t1 < t0:
            raise ValueError("end must be greater than or equal to start")

        parameters: dict[str, Any] = {
            "t0": t0,
            "t1": t1,
            "limit": limit_number,
            "sort": sort_value,
            "media": media_number,
            "format": response_format,
        }
        if measurement_set is not None:
            code = str(measurement_set).strip()
            if not code:
                raise ValueError("measurement_set may not be empty")
            parameters["metering_code"] = code
            parameters["measurement_set_id"] = 0
        else:
            parameters["measurement_set_id"] = int(measurement_set_id)  # type: ignore[arg-type]

        data = self.request("get_values", parameters)
        if response_format == 1:
            if not isinstance(data, Mapping):
                raise APIError(f"Unexpected get_values format=1 response: {data!r}")
            if not _api_bool(data.get("access_granted")):
                raise AuthenticationError(str(data.get("status") or "Access denied"))
            values = data.get("values", data.get("Values", []))
        else:
            values = data

        if values is None:
            values = []
        if not isinstance(values, list):
            raise APIError(f"Unexpected get_values response: {values!r}")

        frame = pd.DataFrame(values)
        if frame.empty:
            return pd.DataFrame(
                {
                    "datetime_utc": pd.Series([], dtype="datetime64[ns, UTC]"),
                    "timestamp": pd.Series([], dtype="int64"),
                    "value": pd.Series([], dtype="float64"),
                }
            )
        missing = {"timestamp", "value"}.difference(frame.columns)
        if missing:
            raise APIError(
                "get_values response is missing required field(s): "
                + ", ".join(sorted(missing))
            )
        try:
            frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="raise").astype("int64")
            frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        except (TypeError, ValueError) as exc:
            raise APIError("get_values returned invalid timestamp or value data") from exc
        frame.insert(
            0,
            "datetime_utc",
            pd.to_datetime(frame["timestamp"], unit="s", utc=True),
        )
        return frame[["datetime_utc", "timestamp", "value"]]
