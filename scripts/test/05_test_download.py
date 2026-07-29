"""Manual test of configured downloads from all enabled sources."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from _bootstrap import PROJECT_ROOT
from vhg_api import load_config
from vhg_api.console import print_header, print_success
from vhg_api.download import download_configured

# A short recent interval keeps this connectivity test lightweight.
END_UTC = datetime.now(timezone.utc).replace(second=0, microsecond=0)
START_UTC = END_UTC - timedelta(hours=4)
WRITE_CSV = True
OUTPUT_DIR = PROJECT_ROOT / "runtime" / "downloads"


def main() -> None:
    print_header("vhg_api - Configured download test")
    config = load_config(
        PROJECT_ROOT / "config" / "settings.yml",
        PROJECT_ROOT / "config" / ".env",
    )

    print(f"Period UTC     : {START_UTC.isoformat()} -> {END_UTC.isoformat()}")
    print(f"Enabled sources: {len(config.active_sources)}")
    print(f"Write CSV      : {'Yes' if WRITE_CSV else 'No'}")
    if WRITE_CSV:
        print(f"Output folder  : {OUTPUT_DIR}")
    print()

    results = download_configured(
        config,
        start=START_UTC,
        end=END_UTC,
        output_dir=OUTPUT_DIR,
        write_csv=WRITE_CSV,
    )

    print("Downloaded sources")
    print("------------------")
    for result in results:
        source = result.source
        frame = result.data
        first = frame["datetime_utc"].min() if not frame.empty else "-"
        last = frame["datetime_utc"].max() if not frame.empty else "-"
        print(
            f"{source.station:>6}  {source.variable:<10} "
            f"set={source.measurement_set:<12} media={source.media:<4} "
            f"rows={len(frame):>6}  {first} -> {last}\n"
            f"        destination={source.destination}"
        )
        for output_file in result.output_files:
            print(f"        CSV: {output_file}")

    print()
    print_success(f"Configured download test completed for {len(results)} source(s).")


if __name__ == "__main__":
    main()
