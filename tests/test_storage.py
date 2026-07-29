from pathlib import Path

import pandas as pd

from vhg_api.storage import incremental_start, update_raw_archive


def raw_frame(times: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "datetime_utc": pd.to_datetime(times, utc=True),
        "value": values,
        "station": "VX",
        "series_id": "145_VX",
        "variable": "H",
        "measurement_set": "VX_",
        "media": 6,
    })


def test_update_raw_archive_merges_sorts_and_keeps_newest(tmp_path: Path) -> None:
    path = tmp_path / "145_VX_H_2026.csv"
    update_raw_archive(
        raw_frame(["2026-01-01T00:05:00Z", "2026-01-01T00:00:00Z"], [2.0, 1.0]),
        path,
    )
    merged = update_raw_archive(
        raw_frame(["2026-01-01T00:05:00Z", "2026-01-01T00:10:00Z"], [2.5, 3.0]),
        path,
    )
    assert merged["value"].tolist() == [1.0, 2.5, 3.0]
    assert merged["datetime_utc"].is_monotonic_increasing
    reread = pd.read_csv(path, sep=";")
    assert list(reread.columns) == [
        "timestamp", "datetime_utc", "value", "station", "series_id",
        "variable", "measurement_set", "media",
    ]
    assert reread["timestamp"].tolist() == [1767225600, 1767225900, 1767226200]


def test_incremental_start_uses_overlap_without_preceding_lower_bound(tmp_path: Path) -> None:
    path = tmp_path / "raw.csv"
    update_raw_archive(raw_frame(["2026-01-02T00:00:00Z"], [1.0]), path)
    assert incremental_start("2026-01-01T00:00:00Z", path, overlap_minutes=1440) == pd.Timestamp("2026-01-01T00:00:00Z")
    assert incremental_start("2025-12-01T00:00:00Z", path, overlap_minutes=60) == pd.Timestamp("2026-01-01T23:00:00Z")


def test_update_migrates_archive_without_timestamp_column(tmp_path: Path) -> None:
    path = tmp_path / "legacy_raw.csv"
    raw_frame(["2026-01-01T00:00:00Z"], [1.0]).to_csv(path, sep=";", index=False)

    merged = update_raw_archive(
        raw_frame(["2026-01-01T00:05:00Z"], [2.0]), path
    )

    assert list(merged.columns)[0:2] == ["timestamp", "datetime_utc"]
    assert merged["timestamp"].tolist() == [1767225600, 1767225900]
    assert "timestamp" in pd.read_csv(path, sep=";").columns
