"""Test the unauthenticated TDS ping operation. Run with F5 in Spyder."""

from __future__ import annotations

from _bootstrap import PROJECT_ROOT
from vhg_api.client import TDSClient
from vhg_api.config import ConfigError, load_config
from vhg_api.console import print_error, print_header, print_success
from vhg_api.errors import VHGAPIError

SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yml"
ENV_FILE = PROJECT_ROOT / "config" / ".env"


def main() -> None:
    print_header("vhg_api - Ping test")
    try:
        config = load_config(SETTINGS_FILE, ENV_FILE)
        with TDSClient(config) as client:
            print(f"API URL: {client.url}")
            client.ping()
    except (ConfigError, VHGAPIError) as exc:
        print_error(str(exc))
        return

    print_success("Server replied with pong.")
    print("\nNext manual test: scripts/test/04_test_access.py")


if __name__ == "__main__":
    main()
