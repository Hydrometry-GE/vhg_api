from pathlib import Path

from vhg_api.config import (
    ApiConfig, AppConfig, IncrementalConfig, MeasurementSource,
    ProxyConfig, StorageConfig,
)
from vhg_api.runner import run_download


def make_config(tmp_path: Path) -> AppConfig:
    source = MeasurementSource(
        True, "VX", "145_VX", "VX_", "H", 6,
        "01_Rivieres/stations/145_VX/raw_data/H", 2,
    )
    return AppConfig(
        profile="test",
        api=ApiConfig("example.test", "/api", "u", "1", "x", 30),
        proxy=ProxyConfig(False, None, None),
        storage=StorageConfig(
            tmp_path, "{series_id}_{variable}_{year}_raw.csv",
            tmp_path / "logs",
        ),
        incremental=IncrementalConfig(30, "2025-01-01T00:00:00Z"),
        settings_file=tmp_path / "settings.yml",
        sources_file=tmp_path / "sources.csv",
        sources=(source,),
        stations=(),
    )


def test_dry_run_selects_sources_without_writing(tmp_path: Path) -> None:
    summary = run_download(make_config(tmp_path), dry_run=True)
    assert summary.succeeded == 1
    assert summary.failed == 0
    assert summary.rows_downloaded == 0
    assert not list(tmp_path.rglob("*.csv"))


def test_dry_run_respects_filters(tmp_path: Path) -> None:
    summary = run_download(
        make_config(tmp_path), dry_run=True, station="vx", variable="h"
    )
    assert len(summary.results) == 1
    assert summary.results[0].source.series_id == "145_VX"
