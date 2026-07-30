"""Operational download runner for command-line and scheduled executions."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from .client import TDSClient
from .config import AppConfig, MeasurementSource
from .download import download_configured, select_sources


@dataclass(frozen=True)
class SourceRunResult:
    """Outcome of one configured source during an operational run."""

    source: MeasurementSource
    success: bool
    rows_downloaded: int = 0
    output_files: tuple[Path, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class RunSummary:
    """Summary returned by :func:`run_download`."""

    started_at: datetime
    finished_at: datetime
    results: tuple[SourceRunResult, ...]

    @property
    def succeeded(self) -> int:
        """Count successful source executions."""
        return sum(result.success for result in self.results)

    @property
    def failed(self) -> int:
        """Count failed source executions."""
        return len(self.results) - self.succeeded

    @property
    def rows_downloaded(self) -> int:
        """Return the total number of rows received from TDS."""
        return sum(result.rows_downloaded for result in self.results)

    @property
    def output_files(self) -> tuple[Path, ...]:
        """Flatten all yearly output paths written during the run."""
        return tuple(path for result in self.results for path in result.output_files)


def configure_logging(log_dir: Path, *, verbose: bool = False) -> Path:
    """Configure console and daily file logging and return the log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"vhg_api_{datetime.now(timezone.utc):%Y%m%d}.log"
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    return log_path


def _utc_timestamp(value: str | datetime | pd.Timestamp) -> pd.Timestamp:
    """Normalize a datetime-like value to a timezone-aware UTC timestamp."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp


def run_download(
    config: AppConfig,
    *,
    start: str | datetime | pd.Timestamp | None = None,
    end: str | datetime | pd.Timestamp | None = None,
    incremental: bool = True,
    station: str | None = None,
    variable: str | None = None,
    destination: str | None = None,
    dry_run: bool = False,
    continue_on_error: bool = True,
    logger: logging.Logger | None = None,
) -> RunSummary:
    """Download and archive all selected measurement sources.

    Parameters
    ----------
    config:
        Fully resolved application configuration.
    start, end:
        Requested UTC bounds. ``start`` defaults to
        ``incremental.initial_start`` and ``end`` defaults to the current UTC
        minute. Naive datetime values are interpreted as UTC.
    incremental:
        When true, each source may advance ``start`` to its latest archived
        timestamp minus the configured overlap. Set this to false for an
        explicit historical refresh so the requested interval is downloaded
        exactly.
    station, variable, destination:
        Optional exact source filters. Text matching for station and variable is
        case-insensitive; destination matching is exact after path normalization.
    dry_run:
        Resolve and report sources without contacting TDS or writing files.
    continue_on_error:
        Continue with remaining sources after one source fails.
    logger:
        Optional logger, primarily useful to embedding applications and tests.

    Returns
    -------
    RunSummary
        Per-source outcomes and aggregate counts for the completed run.

    Notes
    -----
    Newly downloaded rows are merged after existing rows. Duplicate
    ``datetime_utc`` values therefore retain the newly downloaded record. This
    lets a historical refresh propagate retrospective corrections made in TDS.
    """
    log = logger or logging.getLogger("vhg_api.runner")
    started_at = datetime.now(timezone.utc)
    lower_bound = _utc_timestamp(start or config.incremental.initial_start)
    upper_bound = _utc_timestamp(end or pd.Timestamp.now(tz="UTC").floor("min"))
    if lower_bound > upper_bound:
        raise ValueError(f"Start time {lower_bound} is after end time {upper_bound}")

    selected = select_sources(
        config,
        destination=destination,
        station=station,
        variable=variable,
    )
    log.info(
        "Starting run: %d source(s), start=%s, end=%s, incremental=%s, dry_run=%s",
        len(selected), lower_bound.isoformat(), upper_bound.isoformat(), incremental, dry_run,
    )

    if dry_run:
        results = tuple(SourceRunResult(source=source, success=True) for source in selected)
        for source in selected:
            log.info(
                "DRY RUN %s/%s set=%s media=%s -> %s",
                source.station, source.variable, source.measurement_set,
                source.media, source.destination,
            )
        return RunSummary(started_at, datetime.now(timezone.utc), results)

    outcomes: list[SourceRunResult] = []
    with TDSClient(config) as client:
        for source in selected:
            source_started = time.monotonic()
            log.info(
                "Downloading %s/%s (set=%s, media=%s)",
                source.station, source.variable, source.measurement_set, source.media,
            )
            try:
                downloaded = download_configured(
                    config,
                    start=lower_bound,
                    end=upper_bound,
                    destination=source.destination,
                    station=source.station,
                    variable=source.variable,
                    write_csv=True,
                    merge_existing=True,
                    incremental=incremental,
                    client=client,
                )
                # The combination of destination/station/variable normally identifies
                # one row. Retain support for multiple exact matches defensively.
                rows = sum(len(item.data) for item in downloaded)
                files = tuple(path for item in downloaded for path in item.output_files)
                elapsed = time.monotonic() - source_started
                log.info(
                    "Completed %s/%s: %d row(s), %d file(s), %.1fs",
                    source.station, source.variable, rows, len(files), elapsed,
                )
                outcomes.append(SourceRunResult(source, True, rows, files))
            except Exception as exc:  # operational boundary: log and continue
                elapsed = time.monotonic() - source_started
                log.exception(
                    "Failed %s/%s after %.1fs: %s",
                    source.station, source.variable, elapsed, exc,
                )
                outcomes.append(SourceRunResult(source, False, error=str(exc)))
                if not continue_on_error:
                    break

    summary = RunSummary(started_at, datetime.now(timezone.utc), tuple(outcomes))
    log.info(
        "Run finished: %d succeeded, %d failed, %d row(s), %d file(s), %.1fs",
        summary.succeeded, summary.failed, summary.rows_downloaded,
        len(summary.output_files), (summary.finished_at - summary.started_at).total_seconds(),
    )
    return summary
