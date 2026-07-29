from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from vhg_api.config import (
    ApiConfig, AppConfig, IncrementalConfig, MeasurementSource,
    ProxyConfig, StorageConfig,
)
from vhg_api.download import download_configured, select_sources


def make_config(root: Path = Path("archive")) -> AppConfig:
    sources = (
        MeasurementSource(True, "VX", "145_VX", "VX", "H", 6, "01_Rivieres/stations/145_VX/raw_data/H", 2),
        MeasurementSource(True, "VX", "145_VX", "VX", "Q", 16, "01_Rivieres/stations/145_VX/raw_data/Q", 3),
        MeasurementSource(False, "VX", "145_VX", "VX", "BAT", 100, "runtime/technical/VX/BAT", 4),
        MeasurementSource(True, "AR", "AR", "AR_", "P", 1, "03_Pluie/stations/AR/raw_data/P", 5),
    )
    return AppConfig(
        profile="test",
        api=ApiConfig("example.test", "/api", "u", "1", "x", 30),
        proxy=ProxyConfig(False, None, None),
        storage=StorageConfig(root, "{series_id}_{variable}_{year}_raw.csv", Path("logs")),
        incremental=IncrementalConfig(30),
        settings_file=Path("settings.yml"),
        sources_file=Path("sources.csv"),
        sources=sources,
        stations=(),
    )


class FakeClient:
    def __init__(self, dates: list[str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.dates = dates or ["2026-01-01T00:00:00Z"]

    def get_values(self, **kwargs: Any) -> pd.DataFrame:
        self.calls.append(kwargs)
        return pd.DataFrame({
            "datetime_utc": pd.to_datetime(self.dates),
            "timestamp": range(len(self.dates)),
            "value": [1.5] * len(self.dates),
        })

    def close(self) -> None:
        raise AssertionError("Injected client must not be closed")


def test_select_sources_defaults_to_all_enabled_rows_in_order() -> None:
    selected = select_sources(make_config())
    assert [(s.station, s.variable) for s in selected] == [("VX", "H"), ("VX", "Q"), ("AR", "P")]


def test_select_sources_can_filter_destination() -> None:
    selected = select_sources(make_config(), destination="03_Pluie/stations/AR/raw_data/P")
    assert [(s.station, s.variable) for s in selected] == [("AR", "P")]


def test_download_configured_resolves_sources_csv_rows() -> None:
    client = FakeClient()
    results = download_configured(
        make_config(), start="2026-01-01", end="2026-01-02",
        station="VX", client=client,
    )
    assert len(results) == 2
    assert [call["media"] for call in client.calls] == [6, 16]
    assert all(call["measurement_set"] == "VX" for call in client.calls)


def test_download_adds_canonical_source_columns() -> None:
    client = FakeClient()
    result = download_configured(
        make_config(), start="2026-01-01", end="2026-01-02",
        station="VX", variable="H", client=client,
    )[0]
    assert list(result.data.columns) == [
        "timestamp", "datetime_utc", "value", "station", "series_id",
        "variable", "measurement_set", "media",
    ]
    row = result.data.iloc[0]
    assert row["timestamp"] == 1767225600
    assert row["station"] == "VX"
    assert row["series_id"] == "145_VX"
    assert row["variable"] == "H"
    assert row["measurement_set"] == "VX"
    assert row["media"] == 6


def test_incremental_download_applies_configured_overlap(tmp_path: Path) -> None:
    from vhg_api.storage import update_raw_archive
    archive = tmp_path / "145_VX_H_2026_raw.csv"
    update_raw_archive(pd.DataFrame({
        "datetime_utc": pd.to_datetime(["2026-01-02T00:00:00Z"]),
        "value": [1.0], "station": ["VX"], "series_id": ["145_VX"],
        "variable": ["H"], "measurement_set": ["VX"], "media": [6],
    }), archive)
    client = FakeClient()
    download_configured(
        make_config(), start="2026-01-01T00:00:00Z", end="2026-01-03T00:00:00Z",
        station="VX", variable="H", output_dir=tmp_path,
        write_csv=False, incremental=True, client=client,
    )
    assert client.calls[0]["start"] == pd.Timestamp("2026-01-01T23:30:00Z")


def test_row_destination_routing_is_generic(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    river = download_configured(
        config, start="2026-01-01", end="2026-01-02",
        station="VX", variable="H", write_csv=True, client=FakeClient(),
    )[0]
    rain = download_configured(
        config, start="2026-01-01", end="2026-01-02",
        station="AR", write_csv=True, client=FakeClient(),
    )[0]
    assert river.output_file == tmp_path / "01_Rivieres/stations/145_VX/raw_data/H/2026/145_VX_H_2026_raw.csv"
    assert rain.output_file == tmp_path / "03_Pluie/stations/AR/raw_data/P/2026/AR_P_2026_raw.csv"
    assert river.output_file.exists()
    assert rain.output_file.exists()


def test_download_is_split_into_yearly_files(tmp_path: Path) -> None:
    result = download_configured(
        make_config(tmp_path), start="2025-12-31", end="2026-01-02",
        station="VX", variable="H", write_csv=True,
        client=FakeClient(["2025-12-31T23:55:00Z", "2026-01-01T00:00:00Z"]),
    )[0]
    assert len(result.output_files) == 2
    assert {path.name for path in result.output_files} == {
        "145_VX_H_2025_raw.csv", "145_VX_H_2026_raw.csv"
    }


def test_absolute_destination_bypasses_data_root(tmp_path: Path) -> None:
    absolute_destination = (tmp_path / "direct" / "VX" / "H").as_posix()
    source = MeasurementSource(
        True, "VX", "145_VX", "VX", "H", 6, absolute_destination, 2
    )
    base = make_config(Path("unused_root"))
    config = AppConfig(
        profile=base.profile, api=base.api, proxy=base.proxy,
        storage=StorageConfig(None, base.storage.filename, base.storage.log_dir),
        incremental=base.incremental, settings_file=base.settings_file,
        sources_file=base.sources_file, sources=(source,), stations=(),
    )
    result = download_configured(
        config, start="2026-01-01", end="2026-01-02",
        write_csv=True, client=FakeClient(),
    )[0]
    assert result.output_file == tmp_path / "direct/VX/H/2026/145_VX_H_2026_raw.csv"
    assert result.output_file.exists()
