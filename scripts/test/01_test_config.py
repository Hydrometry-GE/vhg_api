"""Load and display the complete configuration. Run with F5 in Spyder."""

from __future__ import annotations

from _bootstrap import PROJECT_ROOT
from vhg_api.config import ConfigError, load_config
from vhg_api.console import print_error, print_header, print_subheader, print_success

SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yml"
ENV_FILE = PROJECT_ROOT / "config" / ".env"


def main() -> None:
    print_header("vhg_api - Configuration test")
    print(f"Settings : {SETTINGS_FILE}")
    print(f"Sources  : {SETTINGS_FILE.parent / 'sources.csv'}")
    print(f"Env file : {ENV_FILE}")

    try:
        config = load_config(SETTINGS_FILE, ENV_FILE)
    except ConfigError as exc:
        print()
        print_error(str(exc))
        print("\nConfiguration test failed.")
        return

    print_subheader("Deployment")
    print(f"Profile      : {config.profile}")
    print(f"Server       : {config.api.server}")
    print(f"Endpoint     : {config.api.endpoint}")
    print(f"Proxy enabled: {config.proxy.enabled}")
    print(f"Archive root : {config.storage.root}")
    print(f"Log folder   : {config.storage.log_dir}")
    print(f"Overlap      : {config.incremental.overlap_minutes} minutes")

    print_subheader("Stations and sources")
    for station in config.stations:
        print(f"{station.code} ({station.series_id})")
        for source in station.sources:
            status = "enabled" if source.enabled else "disabled"
            print(
                f"  {source.measurement_set:<10} "
                f"{source.variable:<10} media {source.media:<4} [{status}]\n"
                f"      -> {source.destination}"
            )

    print()
    print_success(
        f"Configuration valid: {len(config.stations)} station(s), "
        f"{len(config.sources)} source(s), {len(config.active_sources)} active source(s)."
    )


if __name__ == "__main__":
    main()
