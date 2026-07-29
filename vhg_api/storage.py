"""Storage helpers for immutable-source raw hydrometric data.

The storage layer is deliberately independent from the TDS client.  It accepts
already downloaded data, validates the canonical raw schema, and safely updates
an existing CSV archive by timestamp.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd


RAW_COLUMNS = (
    "timestamp",
    "datetime_utc",
    "value",
    "station",
    "series_id",
    "variable",
    "measurement_set",
    "media",
)


def normalize_raw_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Return a validated copy using the canonical raw-data column order.

    ``datetime_utc`` is normalized to timezone-aware UTC and ``timestamp`` is
    regenerated as Unix epoch seconds. Duplicate datetimes inside the incoming
    frame are resolved by retaining the last occurrence. Existing files that
    predate the ``timestamp`` column remain compatible.
    """
    # ``timestamp`` is derived from ``datetime_utc`` so that older archive
    # files without the convenience column remain readable and are migrated
    # automatically on their next update.
    required_columns = tuple(column for column in RAW_COLUMNS if column != "timestamp")
    missing = [column for column in required_columns if column not in data.columns]
    if missing:
        raise ValueError(f"Raw data are missing required column(s): {', '.join(missing)}")

    frame = data.loc[:, required_columns].copy()
    frame["datetime_utc"] = pd.to_datetime(frame["datetime_utc"], utc=True, errors="raise")
    frame.insert(
        0,
        "timestamp",
        (frame["datetime_utc"].astype("int64") // 1_000_000_000).astype("int64"),
    )
    frame["media"] = pd.to_numeric(frame["media"], errors="raise").astype("int64")
    frame = frame.drop_duplicates(subset=["datetime_utc"], keep="last")
    frame = frame.sort_values("datetime_utc", kind="stable").reset_index(drop=True)
    return frame


def read_raw_archive(path: str | Path) -> pd.DataFrame:
    """Read and normalize one semicolon-separated raw archive CSV."""
    archive_path = Path(path)
    frame = pd.read_csv(archive_path, sep=";")
    return normalize_raw_frame(frame)


def update_raw_archive(
    data: pd.DataFrame,
    path: str | Path,
    *,
    separator: str = ";",
) -> pd.DataFrame:
    """Merge downloaded rows into a raw archive and rewrite it atomically.

    Existing and new rows are combined, duplicate ``datetime_utc`` values are
    resolved in favour of the newly downloaded row, and the resulting file is
    sorted chronologically. The normalized merged frame is returned.
    """
    archive_path = Path(path)
    incoming = normalize_raw_frame(data)

    if archive_path.exists() and archive_path.stat().st_size > 0:
        existing = read_raw_archive(archive_path)
        combined = pd.concat([existing, incoming], ignore_index=True)
        combined = normalize_raw_frame(combined)
    else:
        combined = incoming

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = archive_path.with_suffix(archive_path.suffix + ".tmp")
    combined.to_csv(
        temporary_path,
        sep=separator,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )
    temporary_path.replace(archive_path)
    return combined


def incremental_start(
    requested_start: str | pd.Timestamp,
    archive_path: str | Path,
    *,
    overlap_minutes: int,
) -> pd.Timestamp:
    """Calculate a safe download start from the latest archived timestamp.

    When the archive does not exist or contains no rows, ``requested_start`` is
    returned. Otherwise the latest stored timestamp minus the configured
    overlap is used, but never a time earlier than ``requested_start``.
    """
    if overlap_minutes < 0:
        raise ValueError("overlap_minutes must be non-negative")

    lower_bound = pd.Timestamp(requested_start)
    if lower_bound.tzinfo is None:
        lower_bound = lower_bound.tz_localize("UTC")
    else:
        lower_bound = lower_bound.tz_convert("UTC")

    path = Path(archive_path)
    if not path.exists() or path.stat().st_size == 0:
        return lower_bound

    existing = read_raw_archive(path)
    if existing.empty:
        return lower_bound

    candidate = existing["datetime_utc"].max() - timedelta(minutes=overlap_minutes)
    return max(lower_bound, candidate)
