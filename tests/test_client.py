from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests

from vhg_api.client import TDSClient, build_api_url
from vhg_api.config import (
    ApiConfig,
    AppConfig,
    IncrementalConfig,
    ProxyConfig,
    StorageConfig,
)
from vhg_api.errors import APIError, AuthenticationError, ConnectionError


class FakeResponse:
    def __init__(self, data: Any, status_code: int = 200, text: str = "") -> None:
        self.data = data
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


class FakeSession(requests.Session):
    def __init__(self, response: FakeResponse) -> None:
        super().__init__()
        self.fake_response = response
        self.last_url: str | None = None
        self.last_json: dict[str, Any] | None = None
        self.last_timeout: int | None = None

    def post(self, url: str, json: dict[str, Any], timeout: int, **_: Any) -> FakeResponse:
        self.last_url = url
        self.last_json = json
        self.last_timeout = timeout
        return self.fake_response


def make_config(proxy: ProxyConfig | None = None) -> AppConfig:
    return AppConfig(
        profile="test",
        api=ApiConfig(
            server="example.test",
            endpoint="/io/web_service_json.php",
            username="user",
            dossier_id="42",
            encrypted_password="encrypted",
            timeout_seconds=30,
        ),
        proxy=proxy or ProxyConfig(False, None, None),
        storage=StorageConfig(Path("archive"), "{series_id}_{variable}_{year}_raw.csv", Path("logs")),
        incremental=IncrementalConfig(30),
        settings_file=Path("settings.yml"),
        sources_file=Path("sources.csv"),
        sources=(),
        stations=(),
    )


def test_build_api_url_adds_https() -> None:
    assert build_api_url("example.test", "/io/web_service_json.php") == (
        "https://example.test/io/web_service_json.php"
    )


def test_ping_is_not_authenticated() -> None:
    session = FakeSession(FakeResponse({"ping": "pong"}))
    client = TDSClient(make_config(), session=session, retry_total=0)

    assert client.ping() is True
    assert session.last_json == {"operation": "ping"}
    assert session.trust_env is False


def test_check_access_adds_security_fields() -> None:
    session = FakeSession(
        FakeResponse(
            {
                "access_granted": 1,
                "view": "0",
                "manage": "0",
                "import_data": "0",
                "export_data": "1",
            }
        )
    )
    client = TDSClient(make_config(), session=session, retry_total=0)

    rights = client.check_access()

    assert rights.access_granted is True
    assert rights.export_data is True
    assert rights.manage is False
    assert session.last_json is not None
    assert session.last_json["operation"] == "check_access"
    assert session.last_json["username"] == "user"
    assert len(str(session.last_json["challenge_password"])) == 64


def test_proxy_is_only_applied_when_enabled() -> None:
    session = FakeSession(FakeResponse({"ping": "pong"}))
    proxy = ProxyConfig(True, "http://proxy:8080", "http://proxy:8080")
    TDSClient(make_config(proxy), session=session, retry_total=0)
    assert session.proxies == {
        "http": "http://proxy:8080",
        "https": "http://proxy:8080",
    }


def test_denied_access_raises_authentication_error() -> None:
    session = FakeSession(FakeResponse({"access_granted": "0"}))
    client = TDSClient(make_config(), session=session, retry_total=0)
    with pytest.raises(AuthenticationError, match="did not grant access"):
        client.check_access()


def test_invalid_json_raises_api_error() -> None:
    session = FakeSession(FakeResponse(ValueError("bad json"), text="not-json"))
    client = TDSClient(make_config(), session=session, retry_total=0)
    with pytest.raises(APIError, match="invalid JSON"):
        client.ping()


def test_http_error_becomes_connection_error() -> None:
    session = FakeSession(FakeResponse({}, status_code=503))
    client = TDSClient(make_config(), session=session, retry_total=0)
    with pytest.raises(ConnectionError, match="Unable to reach TDS"):
        client.ping()


def test_get_values_accepts_array_response_and_builds_utc_frame() -> None:
    session = FakeSession(FakeResponse([
        {"timestamp": "1709886197", "value": "283.22"},
        {"timestamp": "1709886333", "value": "283.24"},
    ]))
    client = TDSClient(make_config(), session=session, retry_total=0)

    frame = client.get_values(
        measurement_set="VX", media=6,
        start="2024-03-08T00:00:00Z", end="2024-03-09T00:00:00Z"
    )

    assert list(frame.columns) == ["datetime_utc", "timestamp", "value"]
    assert str(frame["datetime_utc"].dtype) == "datetime64[ns, UTC]"
    assert frame["value"].tolist() == [283.22, 283.24]
    assert session.last_json is not None
    assert session.last_json["operation"] == "get_values"
    assert session.last_json["metering_code"] == "VX"
    assert session.last_json["media"] == 6
