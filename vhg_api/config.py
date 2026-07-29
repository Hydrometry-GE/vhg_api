"""Load and validate vhg_api configuration files.

The external configuration is intentionally split into two files:

- ``settings.yml`` for relatively static deployment settings;
- ``sources.csv`` for ordered operational mappings.

The CSV remains easy to edit in Excel, while the normalized in-memory model is
station-centric.
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import ConfigurationError


class ConfigError(ConfigurationError):
    """Backward-compatible name for configuration errors."""


@dataclass(frozen=True)
class ApiConfig:
    """Connection and credential settings required by the TDS API."""
    server: str
    endpoint: str
    username: str
    dossier_id: str
    encrypted_password: str
    timeout_seconds: int


@dataclass(frozen=True)
class ProxyConfig:
    """Optional HTTP and HTTPS proxy settings for outbound requests."""
    enabled: bool
    http: str | None
    https: str | None


@dataclass(frozen=True)
class StorageConfig:
    """Generic destination storage settings."""

    root: Path | None
    filename: str
    log_dir: Path

    @staticmethod
    def is_absolute_destination(destination: str) -> bool:
        """Return whether a destination is absolute on POSIX or Windows."""
        return _is_absolute_destination(destination)

    def raw_file(
        self,
        *,
        destination: str,
        series_id: str,
        station: str,
        variable: str,
        year: int,
    ) -> Path:
        """Resolve a yearly raw-data file from a row-level destination.

        Absolute destinations are used directly. Relative destinations are
        anchored below ``root``; therefore they require a configured root.
        """
        values = {
            "series_id": series_id,
            "station": station,
            "variable": variable,
            "year": year,
        }
        try:
            filename = self.filename.format(**values)
        except KeyError as exc:
            raise ConfigError(
                f"Unknown placeholder {exc.args[0]!r} in storage.filename"
            ) from exc
        destination_path = Path(destination)
        if _is_absolute_destination(destination):
            base = destination_path
        else:
            if self.root is None:
                raise ConfigError(
                    "storage.root (DATA_ROOT) is required for relative destinations"
                )
            base = self.root / destination_path
        return base / str(year) / filename


@dataclass(frozen=True)
class IncrementalConfig:
    """Bounds used to initialize and overlap incremental downloads."""
    overlap_minutes: int
    initial_start: str = "2026-01-01T00:00:00Z"


@dataclass(frozen=True)
class MeasurementSource:
    """One row from ``sources.csv`` after validation and normalization."""
    enabled: bool
    station: str
    series_id: str
    measurement_set: str
    variable: str
    media: int
    destination: str
    row_number: int


@dataclass(frozen=True)
class Station:
    """All configured measurement sources associated with one station code."""
    code: str
    series_id: str
    sources: tuple[MeasurementSource, ...]

    @property
    def active_sources(self) -> tuple[MeasurementSource, ...]:
        """Return only enabled sources while preserving catalogue order."""
        return tuple(source for source in self.sources if source.enabled)


@dataclass(frozen=True)
class AppConfig:
    """Complete normalized application configuration used at runtime."""
    profile: str
    api: ApiConfig
    proxy: ProxyConfig
    storage: StorageConfig
    incremental: IncrementalConfig
    settings_file: Path
    sources_file: Path
    sources: tuple[MeasurementSource, ...]
    stations: tuple[Station, ...]

    @property
    def active_sources(self) -> tuple[MeasurementSource, ...]:
        """Return only enabled sources while preserving catalogue order."""
        return tuple(source for source in self.sources if source.enabled)

    def get_source(
        self, station: str, variable: str
    ) -> MeasurementSource:
        """Return one configured source by station and variable."""
        matches = [
            source for source in self.sources
            if source.station.casefold() == station.strip().casefold()
            and source.variable.casefold() == variable.strip().casefold()
        ]
        if not matches:
            raise ConfigError(
                f"No source configured for station={station!r}, variable={variable!r}"
            )
        if len(matches) > 1:
            raise ConfigError(
                f"Multiple sources configured for station={station!r}, variable={variable!r}"
            )
        return matches[0]


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
_REQUIRED_SOURCE_COLUMNS = (
    "enabled",
    "station",
    "series_id",
    "measurement_set",
    "variable",
    "media",
    "destination",
)


def _load_env_file(path: Path) -> dict[str, str]:
    """Read a simple KEY=VALUE file without mutating ``os.environ``."""
    if not path.exists():
        raise ConfigError(f"Environment file does not exist: {path}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigError(f"Invalid .env line {line_number} in {path}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigError(f"Invalid empty variable name on line {line_number} in {path}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _expand_string(value: str, env: Mapping[str, str], context: str) -> str:
    """Expand ${NAME} and ${NAME:-default} placeholders."""
    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        candidate = env.get(name)
        if candidate not in (None, ""):
            return str(candidate)
        if default is not None:
            return default
        raise ConfigError(f"Missing environment variable {name!r} required by {context}")

    return _ENV_PATTERN.sub(replace, value)


def _expand_tree(value: Any, env: Mapping[str, str], context: str = "settings") -> Any:
    """Recursively expand environment placeholders in YAML-derived values."""
    if isinstance(value, str):
        return _expand_string(value, env, context)
    if isinstance(value, list):
        return [_expand_tree(item, env, context) for item in value]
    if isinstance(value, dict):
        return {key: _expand_tree(item, env, f"{context}.{key}") for key, item in value.items()}
    return value


def _require_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Return a required nested mapping or raise a configuration error."""
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ConfigError(f"Missing or invalid mapping: {key}")
    return value


def _required_text(mapping: Mapping[str, Any], key: str, context: str) -> str:
    """Return a required non-empty value normalized as text."""
    value = mapping.get(key)
    if value is None or str(value).strip() == "":
        raise ConfigError(f"Missing required value: {context}.{key}")
    return str(value).strip()


def _positive_int(mapping: Mapping[str, Any], key: str, context: str) -> int:
    """Parse a required non-negative integer setting."""
    value = mapping.get(key)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{context}.{key} must be an integer; got {value!r}") from exc
    if parsed < 0:
        raise ConfigError(f"{context}.{key} must be non-negative; got {parsed}")
    return parsed


def _parse_bool(value: str, row_number: int, column: str = "enabled") -> bool:
    """Parse a permissive textual boolean from the source catalogue."""
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise ConfigError(f"sources.csv row {row_number}: {column} must be true or false; got {value!r}")


def _is_absolute_destination(value: str) -> bool:
    """Recognize POSIX, Windows-drive, and UNC absolute paths on any OS."""
    from pathlib import PurePosixPath, PureWindowsPath

    candidate = value.strip().replace("\\", "/")
    return (
        PurePosixPath(candidate).is_absolute()
        or PureWindowsPath(candidate).is_absolute()
    )


def _validate_destination(value: str, row_number: int) -> str:
    """Validate and normalize a row-level destination path.

    Absolute POSIX, Windows-drive, and UNC paths are accepted. Relative paths
    remain portable and may not contain ``..`` because they are later anchored
    below ``storage.root``.
    """
    from pathlib import PurePosixPath

    candidate = value.strip().replace("\\", "/")
    if candidate in {"", "."}:
        raise ConfigError(
            f"sources.csv row {row_number}: destination may not be empty"
        )

    posix = PurePosixPath(candidate)
    if not _is_absolute_destination(candidate) and ".." in posix.parts:
        raise ConfigError(
            f"sources.csv row {row_number}: relative destination may not contain '..'"
        )

    # Preserve the leading slash(es) or drive prefix of absolute paths while
    # removing harmless trailing separators.
    normalized = posix.as_posix()
    if normalized not in {"/", "//"}:
        normalized = normalized.rstrip("/")
    return normalized


def _load_sources(path: Path) -> tuple[MeasurementSource, ...]:
    """Read and validate the semicolon-separated source catalogue."""
    if not path.exists():
        raise ConfigError(f"Sources file does not exist: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if reader.fieldnames is None:
            raise ConfigError(f"Sources file has no header: {path}")
        fieldnames = tuple(name.strip() for name in reader.fieldnames)
        missing = [name for name in _REQUIRED_SOURCE_COLUMNS if name not in fieldnames]
        if missing:
            raise ConfigError(f"Sources file is missing required column(s): {', '.join(missing)}")

        sources: list[MeasurementSource] = []
        seen: dict[tuple[str, str, str], int] = {}
        station_identity: dict[str, str] = {}

        for row_number, row in enumerate(reader, start=2):
            cleaned = {str(key).strip(): (value or "").strip() for key, value in row.items()}
            if not any(cleaned.values()):
                continue

            for column in _REQUIRED_SOURCE_COLUMNS:
                if cleaned[column] == "":
                    raise ConfigError(f"sources.csv row {row_number}: {column} may not be empty")

            station = cleaned["station"]
            series_id = cleaned["series_id"]
            measurement_set = cleaned["measurement_set"]
            variable = cleaned["variable"]
            destination = _validate_destination(cleaned["destination"], row_number)

            try:
                media = int(cleaned["media"])
            except ValueError as exc:
                raise ConfigError(
                    f"sources.csv row {row_number}: media must be an integer; got {cleaned['media']!r}"
                ) from exc
            if media < 0:
                raise ConfigError(f"sources.csv row {row_number}: media must be non-negative")

            duplicate_key = (station, measurement_set, variable)
            if duplicate_key in seen:
                raise ConfigError(
                    "Duplicate source mapping for "
                    f"station={station!r}, measurement_set={measurement_set!r}, variable={variable!r} "
                    f"on rows {seen[duplicate_key]} and {row_number}"
                )
            seen[duplicate_key] = row_number

            station_key = station.casefold()
            previous_series_id = station_identity.get(station_key)
            if previous_series_id is not None and previous_series_id != series_id:
                raise ConfigError(
                    f"Station {station!r} uses inconsistent series IDs: "
                    f"{previous_series_id!r} and {series_id!r} (row {row_number})"
                )
            station_identity[station_key] = series_id

            sources.append(
                MeasurementSource(
                    enabled=_parse_bool(cleaned["enabled"], row_number),
                    station=station,
                    series_id=series_id,
                    measurement_set=measurement_set,
                    variable=variable,
                    media=media,
                    destination=destination,
                    row_number=row_number,
                )
            )

    if not sources:
        raise ConfigError(f"Sources file contains no data rows: {path}")
    return tuple(sources)


def _build_stations(sources: tuple[MeasurementSource, ...]) -> tuple[Station, ...]:
    """Group ordered source rows into station-level convenience objects."""
    grouped: dict[str, list[MeasurementSource]] = {}
    series_ids: dict[str, str] = {}
    for source in sources:
        grouped.setdefault(source.station, []).append(source)
        series_ids[source.station] = source.series_id
    return tuple(
        Station(code=station_code, series_id=series_ids[station_code], sources=tuple(items))
        for station_code, items in grouped.items()
    )


def load_config(
    config_file: str | Path = "config/settings.yml",
    env_file: str | Path | None = "config/.env",
) -> AppConfig:
    """Load, expand, validate, and normalize the complete configuration.

    Parameters
    ----------
    config_file:
        YAML settings path.
    env_file:
        Optional .env path. Values from the real process environment take
        precedence over values in this file.
    """
    settings_path = Path(config_file).expanduser().resolve()
    if not settings_path.exists():
        raise ConfigError(f"Settings file does not exist: {settings_path}")

    file_env: dict[str, str] = {}
    if env_file is not None:
        file_env = _load_env_file(Path(env_file).expanduser().resolve())
    # Non-empty process variables override values from the .env file. Empty
    # process variables do not erase an explicitly configured .env value.
    process_env = {key: value for key, value in os.environ.items() if value != ""}
    combined_env = {**file_env, **process_env}

    try:
        raw = yaml.safe_load(settings_path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {settings_path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ConfigError(f"Settings root must be a YAML mapping: {settings_path}")

    data = _expand_tree(raw, combined_env)
    profile = _required_text(data, "profile", "settings")

    api_data = _require_mapping(data, "api")
    proxy_data = _require_mapping(data, "proxy")
    storage_data = _require_mapping(data, "storage")
    incremental_data = _require_mapping(data, "incremental")

    proxy_enabled = proxy_data.get("enabled", False)
    if not isinstance(proxy_enabled, bool):
        raise ConfigError("proxy.enabled must be true or false")

    proxy_http = str(proxy_data.get("http") or "").strip() or None
    proxy_https = str(proxy_data.get("https") or "").strip() or None
    if proxy_enabled and not (proxy_http or proxy_https):
        raise ConfigError(
            "proxy.enabled is true, but neither proxy.http nor proxy.https is defined"
        )

    sources_name = _required_text(data, "sources_file", "settings")
    sources_path = (settings_path.parent / sources_name).resolve()
    sources = _load_sources(sources_path)

    storage_root_text = str(storage_data.get("root") or "").strip()
    storage_root = Path(storage_root_text) if storage_root_text else None
    storage_filename = _required_text(storage_data, "filename", "storage")

    return AppConfig(
        profile=profile,
        api=ApiConfig(
            server=_required_text(api_data, "server", "api"),
            endpoint=_required_text(api_data, "endpoint", "api"),
            username=_required_text(api_data, "username", "api"),
            dossier_id=_required_text(api_data, "dossier_id", "api"),
            encrypted_password=_required_text(api_data, "encrypted_password", "api"),
            timeout_seconds=_positive_int(api_data, "timeout_seconds", "api"),
        ),
        proxy=ProxyConfig(
            enabled=proxy_enabled,
            http=proxy_http if proxy_enabled else None,
            https=proxy_https if proxy_enabled else None,
        ),
        storage=StorageConfig(
            root=storage_root,
            filename=storage_filename,
            log_dir=Path(_required_text(storage_data, "log_dir", "storage")),
        ),
        incremental=IncrementalConfig(
            overlap_minutes=_positive_int(incremental_data, "overlap_minutes", "incremental"),
            initial_start=_required_text(incremental_data, "initial_start", "incremental"),
        ),
        settings_file=settings_path,
        sources_file=sources_path,
        sources=sources,
        stations=_build_stations(sources),
    )
