"""Manual test of row-level destination routing.

Unlike ``05_test_download.py``, this script does not supply ``output_dir``.
Each enabled source is therefore written to the destination configured in
``config/sources.csv``:

- absolute destinations are used directly;
- relative destinations are resolved below ``storage.root`` / ``DATA_ROOT``.

Review the configured destinations before running this script because it may
write into operational archive folders.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from _bootstrap import PROJECT_ROOT
from vhg_api import load_config
from vhg_api.console import print_header, print_success
from vhg_api.download import download_configured

# A short recent interval keeps the routing test lightweight.
END_UTC = datetime.now(timezone.utc).replace(second=0, microsecond=0)
START_UTC = END_UTC - timedelta(hours=4)
WRITE_CSV = True

# Optional filters. Keep both as None to process all enabled sources.
STATION: str | None = None       # e.g. "VX"
VARIABLE: str | None = None      # e.g. "H"


def main() -> None:
    print_header("vhg_api - Destination routing test")
    config = load_config(
        PROJECT_ROOT / "config" / "settings.yml",
        PROJECT_ROOT / "config" / ".env",
    )

    print("WARNING: this test uses destinations from config/sources.csv.")
    print(f"Period UTC      : {START_UTC.isoformat()} -> {END_UTC.isoformat()}")
    print(f"Station filter  : {STATION or 'all'}")
    print(f"Variable filter : {VARIABLE or 'all'}")
    print(f"Write CSV       : {'Yes' if WRITE_CSV else 'No'}")
    print()

    results = download_configured(
        config,
        start=START_UTC,
        end=END_UTC,
        station=STATION,
        variable=VARIABLE,
        write_csv=WRITE_CSV,
    )

    print("Downloaded sources")
    print("------------------")
    for result in results:
        source = result.source
        frame = result.data
        first = frame["datetime_utc"].min() if not frame.empty else "-"
        last = frame["datetime_utc"].max() if not frame.empty else "-"
        destination_kind = (
            "absolute"
            if config.storage.is_absolute_destination(source.destination)
            else "relative"
        )
        print(
            f"{source.station:>6}  {source.variable:<10} "
            f"set={source.measurement_set:<12} media={source.media:<4} "
            f"rows={len(frame):>6}  {first} -> {last}\n"
            f"        destination ({destination_kind})={source.destination}"
        )
        for output_file in result.output_files:
            print(f"        CSV: {output_file}")

    print()
    print_success(f"Destination routing test completed for {len(results)} source(s).")


if __name__ == "__main__":
    main()
