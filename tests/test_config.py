from __future__ import annotations

from pathlib import Path

import pytest

from vhg_api.config import ConfigError, load_config


SETTINGS = """\
profile: test
api:
  server: ${SERVER}
  endpoint: /io/web_service_json.php
  username: ${USER}
  dossier_id: ${DOSSIER}
  encrypted_password: ${PASSWORD}
  timeout_seconds: 60
proxy:
  enabled: false
  http: ${HTTP_PROXY:-}
  https: ${HTTPS_PROXY:-}
storage:
  root: ${DATA_ROOT}
  filename: "{series_id}_{variable}_{year}_raw.csv"
  log_dir: ${LOG_DIR}
incremental:
  initial_start: "2025-01-01T00:00:00Z"
  overlap_minutes: 30
sources_file: sources.csv
"""

ENV = """\
SERVER=example.test
USER=test
DOSSIER=1
PASSWORD=secret
DATA_ROOT=C:/hydrometry
LOG_DIR=C:/runtime/logs
"""


def write_files(tmp_path: Path, sources: str) -> tuple[Path, Path]:
    settings = tmp_path / "settings.yml"
    env = tmp_path / ".env"
    settings.write_text(SETTINGS, encoding="utf-8")
    env.write_text(ENV, encoding="utf-8")
    (tmp_path / "sources.csv").write_text(sources, encoding="utf-8")
    return settings, env


def test_load_config_preserves_order_and_disabled_rows(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;01_Rivieres/stations/145_VX/raw_data/H
true;VX;145_VX;VX;Q;16;01_Rivieres/stations/145_VX/raw_data/Q
false;VX;145_VX;VX;BAT_INT;100;runtime/technical/VX/BAT_INT
"""
    settings, env = write_files(tmp_path, sources)
    config = load_config(settings, env)

    assert [source.variable for source in config.sources] == ["H", "Q", "BAT_INT"]
    assert [source.variable for source in config.active_sources] == ["H", "Q"]
    assert config.stations[0].series_id == "145_VX"
    assert config.sources[0].destination == "01_Rivieres/stations/145_VX/raw_data/H"
    assert config.storage.root == Path("C:/hydrometry")


def test_duplicate_source_is_rejected(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;one
true;VX;145_VX;VX;H;6;two
"""
    settings, env = write_files(tmp_path, sources)
    with pytest.raises(ConfigError, match="Duplicate source mapping"):
        load_config(settings, env)


@pytest.mark.parametrize("destination", ["../outside", "safe/../outside"])
def test_relative_destination_may_not_escape_storage_root(tmp_path: Path, destination: str) -> None:
    sources = f"""enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;{destination}
"""
    settings, env = write_files(tmp_path, sources)
    with pytest.raises(ConfigError, match="destination"):
        load_config(settings, env)



@pytest.mark.parametrize(
    ("destination", "expected"),
    [
        ("/srv/hydrometry/VX/H", "/srv/hydrometry/VX/H"),
        ("D:/Hydrometrie/VX/H", "D:/Hydrometrie/VX/H"),
        ("S:\\Archive\\VX\\H", "S:/Archive/VX/H"),
        (r"\\server\share\hydrometry\VX\H", "//server/share/hydrometry/VX/H"),
    ],
)
def test_absolute_destinations_are_accepted_and_normalized(
    tmp_path: Path, destination: str, expected: str
) -> None:
    sources = f"""enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;{destination}
"""
    settings, env = write_files(tmp_path, sources)
    config = load_config(settings, env)
    assert config.sources[0].destination == expected


def test_data_root_is_optional_when_destination_is_absolute(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;D:/Hydrometrie/VX/H
"""
    settings, env = write_files(tmp_path, sources)
    settings.write_text(SETTINGS.replace("root: ${DATA_ROOT}", "root: ${DATA_ROOT:-}"), encoding="utf-8")
    env.write_text(ENV.replace("DATA_ROOT=C:/hydrometry\n", ""), encoding="utf-8")
    config = load_config(settings, env)
    assert config.storage.root is None
    output = config.storage.raw_file(
        destination=config.sources[0].destination, series_id="145_VX",
        station="VX", variable="H", year=2026,
    )
    assert output.as_posix() == "D:/Hydrometrie/VX/H/2026/145_VX_H_2026_raw.csv"


def test_relative_destination_requires_data_root_at_resolution_time(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;relative/VX/H
"""
    settings, env = write_files(tmp_path, sources)
    settings.write_text(SETTINGS.replace("root: ${DATA_ROOT}", "root: ${DATA_ROOT:-}"), encoding="utf-8")
    env.write_text(ENV.replace("DATA_ROOT=C:/hydrometry\n", ""), encoding="utf-8")
    config = load_config(settings, env)
    with pytest.raises(ConfigError, match="DATA_ROOT.*required"):
        config.storage.raw_file(
            destination=config.sources[0].destination, series_id="145_VX",
            station="VX", variable="H", year=2026,
        )

def test_backslashes_are_normalized_in_destination(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;01_Rivieres\\stations\\145_VX\\raw_data\\H
"""
    settings, env = write_files(tmp_path, sources)
    config = load_config(settings, env)
    assert config.sources[0].destination == "01_Rivieres/stations/145_VX/raw_data/H"


def test_enabled_proxy_requires_an_address(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;test/VX/H
"""
    settings, env = write_files(tmp_path, sources)
    settings.write_text(SETTINGS.replace("enabled: false", "enabled: true"), encoding="utf-8")
    with pytest.raises(ConfigError, match="neither proxy.http nor proxy.https"):
        load_config(settings, env)


def test_disabled_proxy_ignores_defined_addresses(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;test/VX/H
"""
    settings, env = write_files(tmp_path, sources)
    env.write_text(ENV + "HTTP_PROXY=http://proxy.test:8080\nHTTPS_PROXY=http://proxy.test:8080\n", encoding="utf-8")
    config = load_config(settings, env)
    assert config.proxy.enabled is False
    assert config.proxy.http is None
    assert config.proxy.https is None


def test_enabled_proxy_loads_defined_address(tmp_path: Path) -> None:
    sources = """enabled;station;series_id;measurement_set;variable;media;destination
true;VX;145_VX;VX;H;6;test/VX/H
"""
    settings, env = write_files(tmp_path, sources)
    settings.write_text(SETTINGS.replace("enabled: false", "enabled: true"), encoding="utf-8")
    env.write_text(ENV + "HTTPS_PROXY=http://proxy.test:8080\n", encoding="utf-8")
    config = load_config(settings, env)
    assert config.proxy.enabled is True
    assert config.proxy.http is None
    assert config.proxy.https == "http://proxy.test:8080"
