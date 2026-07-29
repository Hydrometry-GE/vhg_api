"""Test authenticated access rights. Run with F5 in Spyder."""

from __future__ import annotations

from _bootstrap import PROJECT_ROOT
from vhg_api.client import TDSClient
from vhg_api.config import ConfigError, load_config
from vhg_api.console import print_error, print_header, print_subheader, print_success
from vhg_api.errors import VHGAPIError

SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yml"
ENV_FILE = PROJECT_ROOT / "config" / ".env"


def yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def main() -> None:
    print_header("vhg_api - Access check test")
    try:
        config = load_config(SETTINGS_FILE, ENV_FILE)
        with TDSClient(config) as client:
            rights = client.check_access()
    except (ConfigError, VHGAPIError) as exc:
        print_error(str(exc))
        return

    print_subheader("Access rights")
    print(f"Access granted: {yes_no(rights.access_granted)}")
    print(f"View          : {yes_no(rights.view)}")
    print(f"Manage        : {yes_no(rights.manage)}")
    print(f"Import data   : {yes_no(rights.import_data)}")
    print(f"Export data   : {yes_no(rights.export_data)}")
    print_success("Authenticated access check completed.")


if __name__ == "__main__":
    main()
