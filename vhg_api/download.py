"""Configuration-aware download helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Iterable

import pandas as pd

from .client import TDSClient
from .config import AppConfig, MeasurementSource
from .errors import DownloadError
from .storage import RAW_COLUMNS, incremental_start, update_raw_archive


@dataclass(frozen=True)
class DownloadResult:
    """Result of downloading one configured source."""

    source: MeasurementSource
    data: pd.DataFrame
    output_files: tuple[Path, ...] = ()

    @property
    def output_file(self) -> Path | None:
        """Backward-compatible shortcut when exactly one file was written."""
        return self.output_files[0] if len(self.output_files) == 1 else None


def _utc_timestamp(value: str | datetime | pd.Timestamp) -> pd.Timestamp:
    """Normalize one datetime-like value to a timezone-aware UTC timestamp."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _chunk_bounds(
    start: str | datetime | pd.Timestamp,
    end: str | datetime | pd.Timestamp,
    *,
    chunk_hours: int,
) -> tuple[tuple[pd.Timestamp, pd.Timestamp], ...]:
    """Split an inclusive UTC interval into consecutive inclusive chunks.

    Adjacent chunks intentionally share their boundary timestamp. The frames
    are concatenated and deduplicated afterwards with ``keep="last"`` so no
    observation can be lost at a chunk boundary.
    """
    if chunk_hours <= 0:
        raise ValueError("download.chunk_hours must be greater than zero")
    lower = _utc_timestamp(start)
    upper = _utc_timestamp(end)
    if lower > upper:
        raise ValueError(f"Start time {lower} is after end time {upper}")

    step = pd.Timedelta(hours=chunk_hours)
    chunks: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    current = lower
    while current < upper:
        chunk_end = min(current + step, upper)
        chunks.append((current, chunk_end))
        current = chunk_end
    if not chunks:
        chunks.append((lower, upper))
    return tuple(chunks)


def _download_in_chunks(
    client: TDSClient,
    source: MeasurementSource,
    *,
    start: str | datetime | pd.Timestamp,
    end: str | datetime | pd.Timestamp,
    chunk_hours: int,
) -> pd.DataFrame:
    """Download one configured source in bounded TDS requests.

    TDS can return incomplete data or server errors for very long ranges,
    especially for dense one-minute series. Chunking keeps every API request
    bounded while remaining transparent to callers.
    """
    chunks = _chunk_bounds(start, end, chunk_hours=chunk_hours)
    log = logging.getLogger("vhg_api.download")
    if len(chunks) > 1:
        log.info(
            "Splitting %s/%s into %d chunk(s) of at most %dh",
            source.station, source.variable, len(chunks), chunk_hours,
        )

    frames: list[pd.DataFrame] = []
    for index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        log.debug(
            "Chunk %d/%d for %s/%s: %s -> %s",
            index, len(chunks), source.station, source.variable,
            chunk_start.isoformat(), chunk_end.isoformat(),
        )
        frame = client.get_values(
            measurement_set=source.measurement_set,
            media=source.media,
            start=chunk_start,
            end=chunk_end,
        )
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame({
            "datetime_utc": pd.Series([], dtype="datetime64[ns, UTC]"),
            "timestamp": pd.Series([], dtype="int64"),
            "value": pd.Series([], dtype="float64"),
        })

    combined = pd.concat(frames, ignore_index=True)
    combined["datetime_utc"] = pd.to_datetime(
        combined["datetime_utc"], utc=True, errors="raise"
    )
    return (
        combined.sort_values("datetime_utc", kind="stable")
        .drop_duplicates(subset=["datetime_utc"], keep="last")
        .reset_index(drop=True)
    )


def select_sources(
    config: AppConfig,
    *,
    destination: str | None = None,
    station: str | None = None,
    variable: str | None = None,
    include_disabled: bool = False,
) -> tuple[MeasurementSource, ...]:
    """Select configured sources while preserving CSV order."""
    sources: Iterable[MeasurementSource] = config.sources if include_disabled else config.active_sources
    destination_filter = destination.strip().replace("\\", "/").casefold() if destination else None
    station_filter = station.strip().casefold() if station else None
    variable_filter = variable.strip().casefold() if variable else None
    selected = tuple(
        source
        for source in sources
        if (destination_filter is None or source.destination.casefold() == destination_filter)
        and (station_filter is None or source.station.casefold() == station_filter)
        and (variable_filter is None or source.variable.casefold() == variable_filter)
    )
    if not selected:
        filters = []
        if destination is not None:
            filters.append(f"destination={destination!r}")
        if station is not None:
            filters.append(f"station={station!r}")
        if variable is not None:
            filters.append(f"variable={variable!r}")
        detail = ", ".join(filters) if filters else "the requested selection"
        raise DownloadError(f"No configured sources match {detail}")
    return selected


def _output_path(
    config: AppConfig,
    source: MeasurementSource,
    year: int,
    output_dir: str | Path | None,
) -> Path:
    """Resolve one yearly output path, honoring an explicit override."""
    if output_dir is not None:
        return Path(output_dir) / f"{source.series_id}_{source.variable}_{year}_raw.csv"
    return config.storage.raw_file(
        destination=source.destination,
        series_id=source.series_id,
        station=source.station,
        variable=source.variable,
        year=year,
    )


def _candidate_incremental_file(
    config: AppConfig,
    source: MeasurementSource,
    end: str | datetime | pd.Timestamp,
    output_dir: str | Path | None,
) -> Path:
    """Return the yearly file used to determine the incremental start."""
    end_timestamp = pd.Timestamp(end)
    return _output_path(config, source, end_timestamp.year, output_dir)


def _write_yearly(
    frame: pd.DataFrame,
    config: AppConfig,
    source: MeasurementSource,
    *,
    output_dir: str | Path | None,
    merge_existing: bool,
) -> tuple[Path, ...]:
    """Split a canonical frame by UTC year and write each archive file."""
    normalized_dates = pd.to_datetime(frame["datetime_utc"], utc=True)
    output_files: list[Path] = []
    for year in sorted(normalized_dates.dt.year.unique()):
        yearly = frame.loc[normalized_dates.dt.year == year].copy()
        path = _output_path(config, source, int(year), output_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        if merge_existing:
            update_raw_archive(yearly, path)
        else:
            yearly.to_csv(path, sep=";", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
        output_files.append(path)
    return tuple(output_files)


def download_configured(
    config: AppConfig,
    *,
    start: str | datetime | pd.Timestamp,
    end: str | datetime | pd.Timestamp,
    destination: str | None = None,
    station: str | None = None,
    variable: str | None = None,
    output_dir: str | Path | None = None,
    write_csv: bool = False,
    merge_existing: bool = True,
    incremental: bool = False,
    client: TDSClient | None = None,
) -> tuple[DownloadResult, ...]:
    """Download selected configured sources and optionally update yearly CSVs.

    Parameters
    ----------
    config:
        Resolved application configuration and source catalogue.
    start, end:
        UTC interval sent to TDS. These bounds are used directly unless
        ``incremental`` is true.
    destination, station, variable:
        Optional filters applied to enabled rows in ``sources.csv``.
    output_dir:
        Optional directory overriding each row's configured destination. Intended
        mainly for tests and ad-hoc extracts.
    write_csv:
        Write downloaded rows to yearly raw archive files.
    merge_existing:
        Merge into existing files atomically. Newly downloaded rows replace
        existing rows at duplicate timestamps.
    incremental:
        For each source, advance the lower bound to the latest archived timestamp
        minus ``incremental.overlap_minutes``. Historical refresh callers should
        pass false so ``start`` is respected exactly.
    client:
        Optional reusable authenticated client. A temporary client is created and
        closed when omitted.

    Returns
    -------
    tuple[DownloadResult, ...]
        One canonical data frame and its written file paths per selected source.

    Notes
    -----
    Long intervals are transparently split into requests of at most
    ``download.chunk_hours``. Adjacent chunks share their boundary timestamp;
    concatenation and keep-last deduplication remove that intentional overlap.
    Data crossing a UTC calendar-year boundary are split into separate files.
    Relative destinations are anchored below ``storage.root``; absolute
    destinations are used directly.
    """
    selected = select_sources(
        config, destination=destination, station=station, variable=variable
    )
    owns_client = client is None
    active_client = client or TDSClient(config)
    results: list[DownloadResult] = []
    try:
        for source in selected:
            effective_start = start
            if incremental:
                candidate_file = _candidate_incremental_file(
                    config, source, end, output_dir
                )
                effective_start = incremental_start(
                    start,
                    candidate_file,
                    overlap_minutes=config.incremental.overlap_minutes,
                )

            try:
                frame = _download_in_chunks(
                    active_client,
                    source,
                    start=effective_start,
                    end=end,
                    chunk_hours=config.download.chunk_hours,
                )
            except Exception as exc:
                raise DownloadError(
                    f"Failed to download {source.station}/{source.variable} "
                    f"(measurement_set={source.measurement_set!r}, media={source.media})"
                ) from exc

            frame = frame.copy()
            frame["datetime_utc"] = pd.to_datetime(
                frame["datetime_utc"], utc=True, errors="raise"
            )
            frame["timestamp"] = (
                frame["datetime_utc"].astype("int64") // 1_000_000_000
            ).astype("int64")
            frame["station"] = source.station
            frame["series_id"] = source.series_id
            frame["variable"] = source.variable
            frame["measurement_set"] = source.measurement_set
            frame["media"] = source.media
            frame = frame.loc[:, RAW_COLUMNS]

            output_files: tuple[Path, ...] = ()
            if write_csv and not frame.empty:
                output_files = _write_yearly(
                    frame,
                    config,
                    source,
                    output_dir=output_dir,
                    merge_existing=merge_existing,
                )
            results.append(
                DownloadResult(source=source, data=frame, output_files=output_files)
            )
    finally:
        if owns_client:
            active_client.close()
    return tuple(results)
